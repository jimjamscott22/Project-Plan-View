#!/usr/bin/env sh
set -eu

exec uv run python -m launch --reload "$@"