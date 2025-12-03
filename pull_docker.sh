#!/bin/bash

MAX_CONCURRENT=10
FILE="d.txt"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

if [ ! -f "$FILE" ]; then
    echo -e "${RED}File not found: $FILE${NC}"
    exit 1
fi

success=0
failed=0
skipped=0

pull_image() {
    local image="$1"

    # 已存在就跳过
    if docker image inspect "$image" >/dev/null 2>&1; then
        echo -e "${YELLOW}[SKIP]${NC} $image already exists"
        ((skipped++))
        return
    fi

    # ⭐ 新增输出：开始拉取
    echo -e "${BLUE}[PULL]${NC} pulling $image"

    if docker pull "$image" > /dev/null 2>&1; then
        echo -e "${GREEN}[OK]${NC}   $image"
        ((success++))
    else
        echo -e "${RED}[ERR]${NC}  $image"
        ((failed++))
    fi
}

echo "===================================================="
echo "Pulling docker images from $FILE"
echo "Max concurrency: $MAX_CONCURRENT"
echo "===================================================="

while IFS= read -r image || [ -n "$image" ]; do
    [ -z "$image" ] && continue

    while [ "$(jobs -p | wc -l)" -ge "$MAX_CONCURRENT" ]; do
        sleep 1
    done

    pull_image "$image" &
done < "$FILE"

wait

echo "===================================================="
echo -e "${GREEN}Success:${NC} $success"
echo -e "${YELLOW}Skipped:${NC} $skipped"
echo -e "${RED}Failed:${NC}  $failed"
echo "===================================================="
