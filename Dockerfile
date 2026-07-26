# AssistantAMU — image d'exécution de l'API (PRD §5.3.6).
#
# Construit une image CPU autonome : dépendances figées par uv.lock, modèle
# d'embeddings embarqué, API servie par uvicorn sur le port 8000.
#
#   docker build -t assistant-amu .
#   docker run --rm -p 8000:8000 -v assistant-amu-data:/data assistant-amu
#   → http://127.0.0.1:8000/  (page de démonstration)  ·  /docs  ·  /health
#
# L'index vectoriel n'est pas dans l'image (il se régénère depuis le corpus) :
# il vit dans le volume /data. Pour le construire, monter corpus/raw/ puis
# lancer l'ingestion dans le conteneur — voir README, « Exécution par conteneur ».
FROM python:3.12-slim

# uv épinglé à la version de développement : même résolveur des deux côtés.
COPY --from=ghcr.io/astral-sh/uv:0.11.14 /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Le code déduit la racine du projet de l'emplacement des sources : prompts/,
    # demo.html et corpus/ sont lus à côté de src/. L'arborescence est donc
    # conservée telle quelle et rendue importable, plutôt qu'installée en paquet.
    PYTHONPATH=/app/src \
    # Modèle d'embeddings embarqué dans l'image, lu depuis ce cache au démarrage.
    HF_HOME=/opt/huggingface \
    # Index vectoriel et données mutables : dans le volume, jamais dans l'image.
    CHROMA_PATH=/data/chroma_db \
    # Depuis un conteneur, « localhost » désigne le conteneur lui-même : le
    # backend local tourne sur l'hôte (F5 — sinon /health le signale injoignable).
    OLLAMA_BASE_URL=http://host.docker.internal:11434

WORKDIR /app

# 1. Dépendances figées, d'abord et seules : cette couche n'est reconstruite que
#    si pyproject.toml ou uv.lock changent, pas à chaque modification du code.
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --no-emit-project --no-hashes -o /tmp/req.txt \
    # Le lock épingle, pour Linux, la variante CUDA de torch : 16 roues
    # nvidia-*/triton pour ~2,5 Go, inutiles ici puisque l'inférence est CPU
    # (PRD §9 : latences mesurées sur CPU). On les retire et on installe la
    # roue CPU de la même version, depuis l'index PyTorch dédié.
    && grep -vE '^(nvidia-|triton==)' /tmp/req.txt > /tmp/req-cpu.txt \
    && TORCH_VERSION="$(sed -n 's/^torch==\([0-9a-z.]*\).*/\1/p' /tmp/req.txt)" \
    && uv pip install --system --index-url https://download.pytorch.org/whl/cpu \
        "torch==${TORCH_VERSION}" \
    && uv pip install --system -r /tmp/req-cpu.txt \
    && rm -rf /root/.cache

# 2. Modèle d'embeddings (~470 Mo) téléchargé à la construction : le conteneur
#    démarre ensuite sans réseau et aucune requête ne paie le téléchargement.
#    --build-arg PRELOAD_MODEL=0 produit une image légère qui l'ira chercher au
#    premier appel.
ARG PRELOAD_MODEL=1
ARG EMBEDDING_MODEL=intfloat/multilingual-e5-small
RUN if [ "$PRELOAD_MODEL" = "1" ]; then \
        python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}')" \
        && rm -rf /root/.cache; \
    fi

# 3. Le projet. Le corpus téléchargé (corpus/raw/) reste dehors : seules les
#    sources et leur description sont versionnées, l'image en hérite (PRD §7.1).
COPY src ./src
COPY prompts ./prompts
COPY eval ./eval
COPY corpus/sources.yaml ./corpus/sources.yaml
COPY demo.html README.md ./

RUN mkdir -p /data && useradd --create-home --uid 10001 amu && chown -R amu /data /app
USER amu
VOLUME ["/data"]
EXPOSE 8000

# /health ne lève jamais : il rend 200 en signalant l'état de Chroma et du
# backend LLM. C'est donc un vrai test de vivacité, même sans index ni backend.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import httpx,sys; sys.exit(0 if httpx.get('http://127.0.0.1:8000/health', timeout=4).status_code == 200 else 1)"

CMD ["uvicorn", "assistant_amu.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
