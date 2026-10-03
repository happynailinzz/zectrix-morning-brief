#!/bin/sh
set -eu

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PYTHON="${ZECTRIX_PYTHON:-$PROJECT_DIR/.venv/bin/python}"
OUTPUT="${ZECTRIX_OUTPUT:-/tmp/zectrix-morning-brief.png}"
HOUR="$(date +%H)"

if [ ! -x "$PYTHON" ]; then
    echo "未找到 Python 环境：$PYTHON" >&2
    echo "请先创建虚拟环境并安装 requirements.txt" >&2
    exit 1
fi

case "$HOUR" in
    07|16) MODE="" ;;
    21) MODE="--tomorrow" ;;
    *)
        echo "当前时间 ${HOUR}:xx 不在计划时段（07:00、16:00、21:00），跳过"
        exit 0
        ;;
esac

cd "$PROJECT_DIR"
exec "$PYTHON" scripts/morning_brief.py --output "$OUTPUT" $MODE
