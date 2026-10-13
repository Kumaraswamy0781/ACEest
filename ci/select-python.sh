#!/bin/sh
# Select an installed interpreter without changing the OS default Python.
set -eu
for candidate in python3.12 python3.11 python3.10 python3; do
    if candidate_path=$(command -v "$candidate" 2>/dev/null); then
        if "$candidate_path" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
            printf '%s\n' "$candidate_path"
            exit 0
        fi
    fi
done
printf '%s\n' 'No Python 3.10+ interpreter is available to Jenkins. Install Python 3.12 and pip on this agent, then rebuild.' >&2
exit 1
