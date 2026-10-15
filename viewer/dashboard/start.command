#!/bin/zsh
set -eu
project_dir="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$project_dir"
export PYTHONPATH="$project_dir/src"
exec "$project_dir/.venv/bin/python" -B -m finarch.dashboard.viewer.server --open "$@"
