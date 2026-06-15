#!/bin/bash

set -euo pipefail

BRANCH="${DEPLOY_BRANCH:-main}"
COMMIT_MSG="${1:-}"

if [ -z "$COMMIT_MSG" ]; then
    read -r -p "请输入本次提交说明 (回车使用默认: update papers): " input
    COMMIT_MSG="${input:-update papers}"
fi

cd "$(git rev-parse --show-toplevel)"

CURRENT_BRANCH="$(git branch --show-current)"
if [ "$CURRENT_BRANCH" != "$BRANCH" ]; then
    echo "当前分支是 $CURRENT_BRANCH，请先切换到 $BRANCH 后再运行。"
    exit 1
fi

echo "开始同步远端 $BRANCH..."
git fetch origin "$BRANCH"
git pull --rebase --autostash origin "$BRANCH"

echo "暂存项目文件..."
git add -- \
    .github/workflows/*.yml \
    README.md \
    requirements.txt \
    deploy.sh \
    update_papers.py \
    update_citations.py \
    generate_report.py \
    app.js \
    citations_map.js \
    style.css \
    citations_map.css \
    index.html \
    citations.html \
    about.md \
    data*.json \
    my_papers.json \
    geocode_cache.json

if git diff --cached --quiet; then
    echo "没有检测到需要提交的项目文件变更。"
    exit 0
fi

echo "提交更改..."
git commit -m "$COMMIT_MSG"

echo "推送到 GitHub..."
git push origin "$BRANCH"

echo "推送完成。"
