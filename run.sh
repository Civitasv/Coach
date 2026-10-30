#!/usr/bin/env sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

if [ -n "${COACH_PYTHON:-}" ]; then
    exec "$COACH_PYTHON" scripts/bootstrap.py "$@"
fi
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
        exec "$candidate" scripts/bootstrap.py "$@"
    fi
done
printf '%s\n' 'Coach requires Python 3.11+; install it and rerun ./run.sh.' >&2
exit 1