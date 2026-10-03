#!/bin/sh
set -eu

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PYTHON="${ZECTRIX_PYTHON:-$PROJECT_DIR/.venv/bin/python}"
OUTPUT="${ZECTRIX_OUTPUT:-/tmp/zectrix-morning-brief.png}"

if [ ! -x "$PYTHON" ]; then
    echo "未找到 Python 环境：$PYTHON" >&2
    echo "请先创建虚拟环境并安装 requirements.txt" >&2
    exit 1
fi

cd "$PROJECT_DIR"
exec "$PYTHON" scripts/morning_brief.py --output "$OUTPUT"
