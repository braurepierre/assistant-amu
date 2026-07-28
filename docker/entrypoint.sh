#!/bin/sh
# Restore the vector index before serving, then hand over to the command.
#
# The index is neither versioned nor built into the image: building it needs the
# downloaded corpus, which is not versioned either, so an image build would have
# to fetch third-party sites and two builds of the same commit could differ. It
# travels as an archive instead — produced by
# `python -m assistant_amu.ingestion export`, published once, fetched here.
#
# Nothing happens when the store already holds data: a host with a persistent
# volume restores once and never again. A host without one restores at every
# start, which is the case this exists for.
#
# INDEX_ARCHIVE_URL  address of the .tar.gz. Unset => no restore, and the
#                    service starts on an empty index, which /health reports.
# CHROMA_PATH        where the store lives (set in the image to /data/chroma_db).
set -eu

ARCHIVE_URL="${INDEX_ARCHIVE_URL:-}"
STORE="${CHROMA_PATH:-/data/chroma_db}"

if [ -z "$ARCHIVE_URL" ]; then
    echo "index : INDEX_ARCHIVE_URL absente, aucune restauration."
elif [ -d "$STORE" ] && [ -n "$(ls -A "$STORE" 2>/dev/null)" ]; then
    echo "index : $STORE déjà peuplé, restauration inutile."
else
    echo "index : restauration depuis $ARCHIVE_URL vers $STORE"
    mkdir -p "$STORE"
    # Written next to the store rather than in /tmp: the archive weighs tens of
    # megabytes and /tmp is not always the same filesystem.
    TMP_ARCHIVE="$STORE/../.index-archive.tar.gz"
    if python -c "
import shutil, sys, urllib.request
with urllib.request.urlopen(sys.argv[1], timeout=60) as response, open(sys.argv[2], 'wb') as out:
    shutil.copyfileobj(response, out)
" "$ARCHIVE_URL" "$TMP_ARCHIVE"; then
        tar -xzf "$TMP_ARCHIVE" -C "$STORE"
        rm -f "$TMP_ARCHIVE"
        echo "index : restauré."
    else
        # A failed restore must not stop the service: /ask refuses for lack of
        # sources and /health says the collection is empty, which is a readable
        # state. A container that will not start is not.
        rm -f "$TMP_ARCHIVE"
        echo "index : restauration impossible, démarrage sur un index vide." >&2
    fi
fi

exec "$@"
