#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/build-container.sh" modified "$@"
