r"""Sensibilité du retrieval à la taille du corpus — MESURE SEULE.

Question posée : le recall@5 de 0,86 mesuré sur 19 documents tient-il quand la
botte de foin grossit ? Retrouver le bon document parmi 19 est intrinsèquement
facile ; une part du chiffre vient de là, pas de la qualité de la recherche. Le
risque n°1 documenté pour l'encodeur (PRD §9 : « e5-small dilue les sigles →
retrieval raté sur requêtes lexicales ») est de fait presque intestable à cette
échelle.

Le corpus est donc porté à 29 documents par un lot de 10 pages distractrices
(``corpus/sources_distractors.yaml``) choisies voisines par le vocabulaire et
disjointes par le contenu : elles se disputent les places du top-k sans jamais
répondre à la place du document annoté. Le jeu de questions ne bouge pas.

PRÉDICTION FALSIFIABLE, énoncée avant la mesure. Si l'hypothèse « e5 dilue les
sigles » est la bonne, le sémantique doit reculer plus que BM25 et l'écart
RRF/sémantique se creuser. Si les deux reculent autant, c'est la taille du
corpus qui pèse, pas l'encodeur.

SEUIL, fixé avant la mesure. Le recall bouge par pas de 1/n : 0,02 sur le jeu
facile (50 questions), 0,04 sur le jeu dur (25). Une question peut basculer sur
une quasi-égalité de rang. Un écart n'est retenu qu'à partir de 3 questions —
la barre déjà utilisée pour conclure que la RRF dépassait le sémantique à k=8,
gardée identique pour que les deux résultats restent comparables. Ce n'est pas
un test statistique : c'est un plancher de résolution.

DEUX COLLECTIONS PARALLÈLES, la production intacte. `amu_docs` n'est jamais
ouverte en écriture. Les deux index comparés sont reconstruits dans le même
passage, avec le même embeddeur et le même découpage, puis supprimés : la seule
différence entre les deux chiffres, ce sont les 10 documents. La baseline à 19
documents est reconstruite plutôt que reprise de la collection de production —
plusieurs collections coexistent (500 tokens, 440, `_ctx`) et la provenance d'un
chiffre déjà publié ne se suppose pas.

GARDE-FOUS exécutés avant toute mesure (le script s'arrête si l'un cède) :
  * aucun titre de distracteur ne contient une sous-chaîne réservée par un
    `expected_source` — sinon `chunk_matches` le compterait comme source
    attendue et le recall monterait pour de faux motifs ;
  * aucun fragment de distracteur ne porte CVEC, BCC, LANSAD ni FOAD — les
    quatre questions de sigle n'ont pas d'`expected_source`, n'importe quel
    fragment portant le token y compte comme réussite.

Aucun appel LLM : retrieval pur, rejouable gratuitement.

Run:
    python eval/distractor_experiment.py
    # PowerShell:  .\.venv\Scripts\python.exe eval/distractor_experiment.py
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from assistant_amu.config import PROJECT_ROOT, get_settings
from assistant_amu.evaluation import (
    Question,
    RetrievalRow,
    RrfRetriever,
    evaluate_retrieval,
    load_questions,
)
from assistant_amu.ingestion.download import RAW_DIR, download_all, load_sources
from assistant_amu.ingestion.pipeline import ingest_corpus
from assistant_amu.models import Chunk, RetrievedChunk, SourceDoc
from assistant_amu.retrieval.bm25_store import Bm25Index
from assistant_amu.retrieval.embedder import Embedder
from assistant_amu.retrieval.vector_store import SemanticRetriever, VectorStore

import yaml

SOURCES = PROJECT_ROOT / "corpus" / "sources.yaml"
DISTRACTORS = PROJECT_ROOT / "corpus" / "sources_distractors.yaml"
EASY = PROJECT_ROOT / "eval" / "questions.yaml"
HARD = PROJECT_ROOT / "eval" / "hard_questions.yaml"
REPORTS_DIR = PROJECT_ROOT / "eval" / "reports"

KS = (3, 5, 8)
METHODS = ("semantic", "bm25", "rrf")
THRESHOLD = 3  # questions; below this, an écart is read as noise (see docstring)

# Sigles interrogés sans `expected_source` : un distracteur qui les porte rendrait
# la question satisfiable depuis le mauvais document.
UNANCHORED_SIGLES = ("cvec", "bcc", "lansad", "foad")

# Les trois questions dont le distracteur est volontairement mordant : si elles
# basculent, le fragment récupéré doit être lu avant de conclure.
FLAGGED = {
    "q53": "compte étudiant / identifiants contre « IA web »",
    "q06": "SUIO contre « job » (Droit — vie étudiante)",
    "q29": "SUAPS contre « sportif de haut niveau » (Droit — régimes spéciaux)",
}


# --- Garde-fous ------------------------------------------------------------

def reserved_substrings() -> dict[str, list[str]]:
    """Sous-chaînes de titre réservées par un `expected_source`, et qui les pose."""
    reserved: dict[str, list[str]] = {}
    for path in (EASY, HARD):
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        for entry in data.get("questions", []):
            source = entry.get("expected_source")
            if source:
                reserved.setdefault(source.lower(), []).append(str(entry["id"]))
    return reserved


def check_titles(distractors: list[SourceDoc]) -> list[str]:
    reserved = reserved_substrings()
    return [
        f"{s.title!r} contient {sub!r} (réservé par {', '.join(reserved[sub])})"
        for s in distractors
        for sub in reserved
        if sub in s.title.lower()
    ]


def check_sigles(chunks: list[Chunk], titles: set[str]) -> list[str]:
    faults: list[str] = []
    for chunk in chunks:
        if str(chunk.metadata.get("source_title", "")) not in titles:
            continue
        low = chunk.text.lower()
        for sigle in UNANCHORED_SIGLES:
            if sigle in low:
                faults.append(
                    f"{sigle.upper()} dans un fragment de "
                    f"{chunk.metadata.get('source_title')!r}"
                )
    return faults


# --- Index -----------------------------------------------------------------

def build_store(name: str, chunks: list[Chunk], embedder: Embedder, settings) -> VectorStore:
    """Collection jetable, repartie de zéro (une collection résiduelle fausserait tout)."""
    store = VectorStore(path=settings.chroma_path, collection_name=name, embedder=embedder)
    if store.count():
        store.delete_collection()
        store = VectorStore(path=settings.chroma_path, collection_name=name, embedder=embedder)
    store.add_chunks(chunks)
    return store


def distractor_presence(
    retrievers: dict, questions: list[Question], lot_titles: set[str], fuse_depth: int = 50
) -> dict:
    """Les distracteurs entrent-ils réellement dans le top-k, ou pas du tout ?

    Diagnostic décisif quand le recall ne bouge pas : un écart nul peut signifier
    « la recherche résiste » ou « le lot n'a jamais concouru ». On classe une fois
    à la profondeur de fusion et on lit les rangs — le préfixe d'un classement
    ordonné est le top-k.
    """
    answerable = [q for q in questions if q.answerable]
    out: dict = {"n": len(answerable), "fuse_depth": fuse_depth}
    for method in ("semantic", "bm25"):
        retriever = retrievers[f"d29_{method}"]
        depths = {3: 0, 5: 0, 8: 0}
        in_deep, best, total = 0, None, 0
        for question in answerable:
            ranked = retriever.rank(question.question, fuse_depth)
            positions = [
                i + 1
                for i, chunk in enumerate(ranked)
                if str(chunk.metadata.get("source_title", "")) in lot_titles
            ]
            total += len(positions)
            if positions:
                in_deep += 1
                best = min(positions) if best is None else min(best, min(positions))
            for depth in depths:
                depths[depth] += any(p <= depth for p in positions)
        out[method] = {"depths": depths, "in_deep": in_deep, "best": best, "total": total}
    return out


def build_methods(store: VectorStore) -> dict[str, object]:
    ids, docs, metas = store.get_all()
    semantic = SemanticRetriever(store)
    bm25 = Bm25Index(ids, docs, metas)
    lookup = {
        i: RetrievedChunk(i, str(m.get("doc_id", "")), d, m, 0.0)
        for i, d, m in zip(ids, docs, metas)
    }
    return {"semantic": semantic, "bm25": bm25, "rrf": RrfRetriever(semantic, bm25, lookup)}


# --- Rendu -----------------------------------------------------------------

def _delta(delta: float, n: int) -> str:
    questions = round(delta * n)
    return "±0" if questions == 0 else f"{delta:+.2f} ({questions:+d} q)"


def _truncate(text: str, width: int = 60) -> str:
    text = str(text).replace("|", "\\|").replace("\n", " ")
    return text if len(text) <= width else text[: width - 1] + "…"


def _matrix(title: str, n: int, recalls: dict[int, dict[str, float]]) -> list[str]:
    header = "| Méthode | " + " | ".join(
        f"19 docs k={k} | 29 docs k={k} | Δ k={k}" for k in KS
    ) + " |"
    lines = [
        f"### {title} ({n} questions ; 1 question = {1.0 / n:.3f})",
        "",
        header,
        "|---|" + "|".join("---|---|---" for _ in KS) + "|",
    ]
    for method in METHODS:
        cells = []
        for k in KS:
            before, after = recalls[k][f"d19_{method}"], recalls[k][f"d29_{method}"]
            cells += [f"{before:.2f}", f"{after:.2f}", _delta(after - before, n)]
        lines.append(f"| {method} | " + " | ".join(cells) + " |")
    return lines + [""]


def _changed(rows: list[RetrievalRow], method: str) -> tuple[list, list]:
    lost = [r for r in rows if r.hits[f"d19_{method}"] and not r.hits[f"d29_{method}"]]
    won = [r for r in rows if not r.hits[f"d19_{method}"] and r.hits[f"d29_{method}"]]
    return lost, won


def _worst(recalls: dict[int, dict[str, float]], method: str, n: int) -> tuple[int, int]:
    """Pire écart de la méthode, en questions, et le k où il se produit."""
    deltas = [
        (round((recalls[k][f"d29_{method}"] - recalls[k][f"d19_{method}"]) * n), k)
        for k in KS
    ]
    return min(deltas)


# --- Rapport ---------------------------------------------------------------

def write_report(*, settings, corpus, easy_recall, hard_recall, easy_rows, hard_rows,
                 n_easy, n_hard, easy_presence, hard_presence, tag: str) -> Path:
    today = date.today().isoformat()
    lines = [
        f"# Rapport — sensibilité à la taille du corpus (mesure seule) — {today}",
        "",
        f"- Embeddeur : `{settings.embedding_model}` · découpage "
        f"{settings.chunk_max_tokens} tokens / recouvrement {settings.chunk_overlap}.",
        f"- Collections comparées : `{corpus['name19']}` "
        f"({corpus['docs19']} documents indexés, {corpus['chunks19']} fragments) contre "
        f"`{corpus['name29']}` ({corpus['docs29']} documents indexés, "
        f"{corpus['chunks29']} fragments, +{corpus['added']}).",
        f"- Documents listés : {corpus['listed19']} + {len(corpus['lot'])} distracteurs. "
        f"{corpus['excluded']} exclu(s) à l'ingestion, donc absent(s) des deux index : "
        f"{corpus['excluded_titles']}.",
        "- Les deux index sont reconstruits dans le même passage, même embeddeur et "
        "même découpage : la seule différence mesurée, ce sont les 10 documents. "
        "`amu_docs` (production) n'est jamais ouverte en écriture.",
        "- Le jeu de questions ne bouge pas. Aucun appel LLM.",
        "",
        f"> **Seuil, fixé avant la mesure.** Le recall bouge par pas de "
        f"{1.0 / n_easy:.3f} sur le jeu facile et {1.0 / n_hard:.3f} sur le jeu dur. "
        f"Un écart n'est retenu qu'à partir de **{THRESHOLD} questions** — la barre "
        "déjà utilisée pour conclure que la RRF dépassait le sémantique à k=8. "
        "En deçà, on lit du bruit.",
        "",
        "## Recall@k — 19 documents contre 29",
        "",
    ]
    lines += _matrix("Jeu « facile » (formulations définitionnelles)", n_easy, easy_recall)
    lines += _matrix("Jeu « dur » (formulations conversationnelles)", n_hard, hard_recall)

    # La prédiction, confrontée aux chiffres.
    sem_easy, _ = _worst(easy_recall, "semantic", n_easy)
    bm_easy, _ = _worst(easy_recall, "bm25", n_easy)
    sem_hard, _ = _worst(hard_recall, "semantic", n_hard)
    bm_hard, _ = _worst(hard_recall, "bm25", n_hard)
    def _prediction(sem: int, bm: int) -> str:
        if sem == 0 and bm == 0:
            return "sans objet — aucune des deux ne recule"
        return "vérifiée" if sem < bm else "non vérifiée"

    lines += [
        "## La prédiction énoncée avant la mesure",
        "",
        "« Si e5 dilue les sigles, le sémantique doit reculer plus que BM25. »",
        "",
        "| Jeu | pire écart sémantique | pire écart BM25 | prédiction |",
        "|---|---|---|---|",
        f"| facile | {sem_easy:+d} q | {bm_easy:+d} q | {_prediction(sem_easy, bm_easy)} |",
        f"| dur | {sem_hard:+d} q | {bm_hard:+d} q | {_prediction(sem_hard, bm_hard)} |",
        "",
    ]

    # Diagnostic décisif : le lot a-t-il concouru ?
    lines += [
        "## Les distracteurs ont-ils concouru ?",
        "",
        "Un recall inchangé peut signifier deux choses opposées : la recherche "
        "résiste, ou le lot n'est jamais monté assez haut pour la gêner. Ce "
        "diagnostic tranche. Nombre de questions dont le top-k contient au moins "
        "un fragment distracteur, et meilleur rang jamais atteint par le lot.",
        "",
    ]
    for label, presence in (("facile", easy_presence), ("dur", hard_presence)):
        lines += [
            f"### Jeu « {label} » ({presence['n']} questions)",
            "",
            f"| Méthode | top-3 | top-5 | top-8 | top-{presence['fuse_depth']} "
            "(profondeur de fusion) | meilleur rang | fragments cumulés |",
            "|---|---|---|---|---|---|---|",
        ]
        for method in ("semantic", "bm25"):
            stats = presence[method]
            depths = stats["depths"]
            best = f"rang {stats['best']}" if stats["best"] else "jamais classé"
            lines.append(
                f"| {method} | {depths[3]}/{presence['n']} | {depths[5]}/{presence['n']} | "
                f"{depths[8]}/{presence['n']} | {stats['in_deep']}/{presence['n']} | "
                f"{best} | {stats['total']} |"
            )
        lines.append("")
    lines += [
        "> Lecture. Si la colonne top-8 est proche de zéro alors que la colonne "
        f"top-{easy_presence['fuse_depth']} ne l'est pas, le lot perturbe le "
        "classement profond sans atteindre la zone servie à l'utilisateur — ce qui "
        "explique mécaniquement qu'un recall@k≤8 ne bouge pas, et que la RRF, seule "
        "à fusionner à cette profondeur, bouge.",
        "",
    ]

    # Mouvement par question.
    for label, rows, n in (("facile", easy_rows, n_easy), ("dur", hard_rows, n_hard)):
        lines += [f"## Détail par question — jeu « {label} » (k=5)", ""]
        moved = False
        for method in METHODS:
            lost, won = _changed(rows, method)
            if not lost and not won:
                continue
            moved = True
            lines += [
                f"**{method}** — perdues : {len(lost)} · regagnées : {len(won)}",
                "",
                "| id | question | 19 docs | 29 docs | à trier |",
                "|---|---|---|---|---|",
            ]
            for row in lost + won:
                flag = f"⚠ {FLAGGED[row.id]}" if row.id in FLAGGED else ""
                lines.append(
                    f"| {row.id} | {_truncate(row.question)} | "
                    f"{'✅' if row.hits[f'd19_{method}'] else '❌'} | "
                    f"{'✅' if row.hits[f'd29_{method}'] else '❌'} | {flag} |"
                )
            lines.append("")
        if not moved:
            lines += ["Aucune question ne change de statut sur ce jeu.", ""]

    lines += [
        "> **Ce qu'une bascule ne dit pas.** Un recall qui baisse signifie que le "
        "document *annoté* est sorti du top-k, pas nécessairement qu'une mauvaise "
        "réponse serait produite : un distracteur peut avoir pris sa place en "
        "répondant tout aussi bien. Le lot a été choisi disjoint par le contenu "
        "pour rendre ce cas rare, mais trois questions restent exposées "
        "(marquées ⚠ ci-dessus) et demandent la lecture du fragment récupéré.",
        "",
    ]

    lines += _conclusion(easy_recall, hard_recall, n_easy, n_hard, corpus,
                         easy_presence, hard_presence)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{today}_corpus_scaling{tag}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _conclusion(easy_recall, hard_recall, n_easy, n_hard, corpus,
                easy_presence, hard_presence) -> list[str]:
    """Le verdict se déduit des écarts et du seuil, jamais d'un texte écrit d'avance."""
    worst = {}
    for label, recalls, n in (("facile", easy_recall, n_easy), ("dur", hard_recall, n_hard)):
        for method in METHODS:
            questions, k = _worst(recalls, method, n)
            worst[(label, method)] = (questions, k)

    breached = {key: value for key, value in worst.items() if -value[0] >= THRESHOLD}
    if breached:
        key, (questions, k) = min(breached.items(), key=lambda item: item[1][0])
        verdict = (
            f"le passage à {corpus['docs29']} documents **dégrade la recherche de façon "
            f"mesurable** : jusqu'à {-questions} questions perdues (`{key[1]}`, k={k}, "
            f"jeu « {key[0]} »), au-dessus du seuil de {THRESHOLD}"
        )
        decision = (
            "Les chiffres du jour (e5 gagnant, k=5) sont **fragiles au passage à "
            "l'échelle** : ils sont établis sur un corpus assez petit pour flatter la "
            "recherche. Avant tout déploiement, il faut soit élargir le corpus réel et "
            "re-trancher les arbitrages d'encodeur et de k sur cette base, soit assumer "
            "explicitement que le système est validé pour un corpus de l'ordre de 20 "
            "documents."
        )
    else:
        deepest = min(worst.items(), key=lambda item: item[1][0])
        verdict = (
            f"le passage à {corpus['docs29']} documents **ne dégrade pas la recherche "
            f"de façon mesurable** : le pire écart atteint {-deepest[1][0]} question(s) "
            f"(`{deepest[0][1]}`, k={deepest[1][1]}, jeu « {deepest[0][0]} »), sous le "
            f"seuil de {THRESHOLD}"
        )
        decision = (
            f"Les décisions du jour (e5 gagnant, k=5) **résistent** à un corpus porté "
            f"à {corpus['docs29']} documents indexés. C'est un argument de robustesse, "
            "pas une preuve de passage à l'échelle : le corpus reste petit, et le lot "
            "est disjoint par construction du contenu annoté."
        )

    # Le zéro est-il une résistance, ou l'absence de concurrence ?
    top8 = max(
        presence[method]["depths"][8]
        for presence in (easy_presence, hard_presence)
        for method in ("semantic", "bm25")
    )
    deep = max(
        presence[method]["in_deep"]
        for presence in (easy_presence, hard_presence)
        for method in ("semantic", "bm25")
    )
    caveat = (
        f"**Ce que ce zéro vaut vraiment.** Le lot atteint le top-8 sur au plus "
        f"{top8} question(s), alors qu'il entre dans le classement profond "
        f"(top-{easy_presence['fuse_depth']}) sur jusqu'à {deep}. Il perturbe donc la "
        "zone que la RRF fusionne sans jamais atteindre celle qui est servie à "
        "l'utilisateur — ce qui explique mécaniquement l'immobilité du recall@k≤8 et "
        "le fait que la RRF soit la seule méthode à bouger. Conclusion à lire pour ce "
        "qu'elle est : **le critère de sélection a trop bien fonctionné**. Des "
        "documents voisins par le vocabulaire et disjoints par le contenu ne créent "
        "pas la concurrence de tête qu'on voulait mesurer. Tester la dilution des "
        "sigles au sommet du classement demande des documents qui se disputent le "
        "*même* sujet — donc l'arbitrage d'annotation évoqué ci-dessous."
        if top8 <= 2
        else
        f"**Le lot a bien concouru** : il atteint le top-8 sur jusqu'à {top8} "
        f"questions et le classement profond sur {deep}. L'écart mesuré porte donc "
        "sur une concurrence réelle, pas sur un lot resté hors de portée."
    )

    lines = [
        "## Conclusion",
        "",
        f"- Sur ce corpus et ces jeux, {verdict}.",
        "",
        "| Jeu | méthode | pire écart | à quel k |",
        "|---|---|---|---|",
    ]
    for (label, method), (questions, k) in worst.items():
        lines.append(f"| {label} | {method} | {questions:+d} q | {k} |")
    lines += [
        "",
        f"**Portée.** {decision}",
        "",
        caveat,
        "",
        "**Ce que la mesure ne couvre pas.** Le lot est disjoint par le contenu : il "
        "teste la dilution, pas l'ambiguïté entre deux documents qui répondent tous "
        "deux. Le document le plus adverse disponible — un second règlement intérieur, "
        "celui des bibliothèques — a dû être écarté : son titre serait compté comme "
        "source attendue par six questions. L'instruire suppose de resserrer leur "
        "annotation, au prix de la comparabilité avec les rapports datés du 23 juillet.",
        "",
        "**Décision.** Le corpus de production reste à 19 documents "
        "(`corpus/sources.yaml` inchangé) : mesuré, documenté, non branché — même "
        "régime que la RRF, la réécriture et la contextualisation.",
        "",
    ]
    return lines


# --- Main ------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", default="", help="suffixe du nom de rapport")
    parser.add_argument("--keep", action="store_true", help="conserver les collections")
    parser.add_argument("--skip-download", action="store_true", help="corpus déjà téléchargé")
    args = parser.parse_args(argv)

    settings = get_settings()
    base, lot = load_sources(SOURCES), load_sources(DISTRACTORS)
    union = base + lot  # ordre gelé : resolve_path localise un fichier par sa position
    base_titles = {s.title for s in base}
    lot_titles = {s.title for s in lot}

    faults = check_titles(lot)
    if faults:
        print("Garde-fou « titres » : le lot collisionne avec des annotations.")
        for fault in faults:
            print(f"  - {fault}")
        return 1
    print(f"garde-fou titres : ok ({len(lot)} distracteurs, 0 collision)")

    if not args.skip_download:
        print(f"téléchargement de {len(union)} sources …")
        results = download_all(union, raw_dir=RAW_DIR)
        counts: dict[str, int] = {}
        for result in results:
            counts[result.status] = counts.get(result.status, 0) + 1
        print("  " + " · ".join(f"{status}={n}" for status, n in sorted(counts.items())))
        for result in results:
            if result.status in ("failed", "blocked-robots"):
                print(f"  ! {result.source.title}: {result.error}")

    chunking = {"max_tokens": settings.chunk_max_tokens, "overlap": settings.chunk_overlap}
    report = ingest_corpus(union, raw_dir=RAW_DIR, **chunking)
    print(report.summary())
    for title, reason in report.excluded:
        print(f"  ! exclu — {title}: {reason}")

    faults = check_sigles(report.chunks, lot_titles)
    if faults:
        print("Garde-fou « sigles » : un distracteur porte un sigle non ancré.")
        for fault in sorted(set(faults)):
            print(f"  - {fault}")
        return 1
    print(f"garde-fou sigles : ok (aucun de {', '.join(s.upper() for s in UNANCHORED_SIGLES)})")

    chunks19 = [c for c in report.chunks if c.metadata.get("source_title") in base_titles]
    chunks29 = report.chunks
    if len(chunks19) == len(chunks29):
        print("! aucun fragment distracteur produit — mesure sans objet.")
        return 1

    # Un seul embeddeur pour les deux collections : mêmes poids, mêmes préfixes.
    embedder = Embedder(settings.embedding_model)
    name19 = f"{settings.chroma_collection}__d19"
    name29 = f"{settings.chroma_collection}__d29"
    store19 = build_store(name19, chunks19, embedder, settings)
    store29 = build_store(name29, chunks29, embedder, settings)
    print(f"index : {name19}={store19.count()} fragments · {name29}={store29.count()}")

    try:
        retrievers = {f"d19_{m}": r for m, r in build_methods(store19).items()}
        retrievers |= {f"d29_{m}": r for m, r in build_methods(store29).items()}

        easy, hard = load_questions(EASY), load_questions(HARD)
        n_easy = sum(1 for q in easy if q.answerable)
        n_hard = sum(1 for q in hard if q.answerable)

        def recalls(questions: list[Question]) -> dict[int, dict[str, float]]:
            return {k: evaluate_retrieval(questions, retrievers, k).recall for k in KS}

        easy_recall, hard_recall = recalls(easy), recalls(hard)
        easy_rows = evaluate_retrieval(easy, retrievers, 5).rows
        hard_rows = evaluate_retrieval(hard, retrievers, 5).rows

        print("diagnostic : les distracteurs entrent-ils dans le top-k ?")
        easy_presence = distractor_presence(retrievers, easy, lot_titles)
        hard_presence = distractor_presence(retrievers, hard, lot_titles)
        for label, presence in (("facile", easy_presence), ("dur", hard_presence)):
            for method in ("semantic", "bm25"):
                stats = presence[method]
                print(
                    f"  [{label}] {method}: top-8 sur {stats['depths'][8]}/{presence['n']} "
                    f"questions · top-{presence['fuse_depth']} sur {stats['in_deep']} "
                    f"· meilleur rang {stats['best']}"
                )

        # Comptes réels : un document listé mais exclu à l'ingestion n'est dans aucun index.
        indexed = {title for title, _, _ in report.processed}
        corpus = {
            "name19": name19, "name29": name29,
            "docs19": len(indexed & base_titles), "docs29": len(indexed),
            "listed19": len(base_titles), "lot": lot,
            "excluded": len(report.excluded),
            "excluded_titles": ", ".join(f"« {t} »" for t, _ in report.excluded) or "aucun",
            "chunks19": len(chunks19), "chunks29": len(chunks29),
            "added": len(chunks29) - len(chunks19),
        }
        path = write_report(
            settings=settings, corpus=corpus, easy_recall=easy_recall,
            hard_recall=hard_recall, easy_rows=easy_rows, hard_rows=hard_rows,
            n_easy=n_easy, n_hard=n_hard, easy_presence=easy_presence,
            hard_presence=hard_presence, tag=args.tag,
        )
        for label, rec in (("facile", easy_recall), ("dur", hard_recall)):
            for k in KS:
                cells = " ".join(
                    f"{m}={rec[k][f'd19_{m}']:.2f}->{rec[k][f'd29_{m}']:.2f}" for m in METHODS
                )
                print(f"  [{label}] k={k} | {cells}")
        print(f"  report: {path}")
    finally:
        if not args.keep:
            store19.delete_collection()
            store29.delete_collection()
    return 0


if __name__ == "__main__":
    sys.exit(main())
