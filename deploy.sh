#!/bin/bash

# 🧊 冰川地震学论文系统 - 一键推送脚本

# 1. 检查是否有 commit 信息输入，如果没有则使用默认信息
COMMIT_MSG=$1
if [ -z "$COMMIT_MSG" ]; then
    read -p "请输入本次提交的说明 (回车使用默认: 'update papers'): " input
    COMMIT_MSG=${input:-"update papers"}
fi

echo "🚀 开始推送更新到 GitHub..."

# 2. 添加所有更改
git add .

# 3. 提交更改
git commit -m "$COMMIT_MSG"

# 4. 推送到远程仓库
# 注意：如果你还没配置 SSH，这里可能会报错
git push

if [ $? -eq 0 ]; then
    echo "✅ 推送成功！"
    echo "🌐 你的网页应该在几分钟后完成更新。"
else
    echo "❌ 推送失败，请检查网络或 GitHub 权限设置。"
    echo "💡 提示：如果提示密码错误，请参考之前的指导配置 SSH 密钥。"
fi
