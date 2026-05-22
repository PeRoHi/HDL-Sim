#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1; then
  python3 start_ui.py "$@"
elif command -v python >/dev/null 2>&1; then
  python start_ui.py "$@"
else
  echo "Python が見つかりません。Python 3.12 をインストールしてください。" >&2
  exit 1
fi
