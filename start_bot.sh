#!/usr/bin/env bash

set -u

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd -- "$SCRIPT_DIR" || exit 1

PYTHON="${PYTHON:-python3}"
if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
    printf '%s\n' "Kepler requires python version 3.10 or newer to run properly." >&2
    exit 1
fi

VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"
REQUIREMENTS_HASH_FILE="$SCRIPT_DIR/.venv/requirements.sha256"
REQUIREMENTS_HASH="$(sha256sum "$SCRIPT_DIR/requirements.txt" | awk '{print $1}')"
INSTALLED_HASH=""

if [ -f "$REQUIREMENTS_HASH_FILE" ]; then
    INSTALLED_HASH="$(cat "$REQUIREMENTS_HASH_FILE")"
fi

if [ ! -x "$VENV_PYTHON" ] || [ "$REQUIREMENTS_HASH" != "$INSTALLED_HASH" ]; then
    if [ ! -x "$VENV_PYTHON" ]; then
        printf '%s\n' "Creating virtual environment..."
        "$PYTHON" -m venv "$SCRIPT_DIR/.venv" || {
            printf '%s\n' "Failed to create virtual environment." >&2
            exit 1
        }
    fi

    printf '%s\n' "Installing dependencies..."
    "$VENV_PYTHON" -m pip install -r "$SCRIPT_DIR/requirements.txt" || {
        printf '%s\n' "Failed to install dependencies." >&2
        exit 1
    }

    printf '%s\n' "$REQUIREMENTS_HASH" > "$REQUIREMENTS_HASH_FILE"
fi

while true; do
    "$VENV_PYTHON" -u main.py
    exit_code=$?

    if [ "$exit_code" -eq 26 ]; then
        printf '%s\n' "Restarting Kepler..."
        continue
    fi

    printf '\nKepler stopped with exit code %s.\n' "$exit_code"
    exit "$exit_code"
done