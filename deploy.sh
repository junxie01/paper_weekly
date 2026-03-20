#!/bin/bash

# 🧊 冰川地震学论文系统 - 一键推送脚本 (增强版)

# 1. 检查是否有 commit 信息输入，如果没有则使用默认信息
COMMIT_MSG=$1
if [ -z "$COMMIT_MSG" ]; then
    read -p "请输入本次提交的说明 (回车使用默认: 'update papers'): " input
    COMMIT_MSG=${input:-"update papers"}
fi

echo "🚀 开始同步更新到 GitHub..."

# 2. 添加所有更改
git add .

# 3. 提交更改 (如果没有任何更改则跳过)
git commit -m "$COMMIT_MSG" || echo "没有检测到需要提交的更改。"

# 4. 先拉取远程更新，防止 [rejected] 错误
echo "📥 正在拉取远程更新并合并本地更改 (rebase)..."
git pull --rebase origin main

# 5. 推送到远程仓库
echo "📤 正在推送数据到 GitHub..."
git push origin main

if [ $? -eq 0 ]; then
    echo "✅ 推送成功！"
    echo "🌐 你的网页应该在几分钟后完成更新。"
else
    echo "❌ 推送失败，请检查网络或是否有未解决的冲突。"
fi
