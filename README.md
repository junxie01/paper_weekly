# 📚 地震学多专题论文周报 (paper_weekly)

一个自动追踪 arXiv 地震学相关研究（DAS、面波、成像、冰川地震等）并自动翻译、生成 PDF 报告并集成至 Hexo 博客的自动化系统。

## 🌐 站点集成说明

由于您的主站位于 `junxie01.github.io`，建议采用以下集成方式：

### 1. 部署为子站点 (推荐)
1. 在本仓库的 **Settings > Pages** 中开启部署，选择 `main` 分支。
2. 您的论文页面将自动出现在：`https://www.seis-jun.xyz/paper_weekly/`
3. 在 Hexo 的 `_config.yml` 菜单中添加该链接即可。

### 2. 自动化流程
- **定时触发**：每周日北京时间上午 8:00 自动运行。
- **手动触发**：在 GitHub Actions 页面点击 "Run workflow"。
- **包含专题**：冰川地震、DAS、面波、地震成像、地震研究。

## 🛠️ 必须完成的配置 (Secrets)

在 GitHub 仓库 **Settings > Secrets and variables > Actions** 中添加：
- `MAIL_USERNAME`: 您的 Gmail 地址 (如 `xxx@gmail.com`)。
- `MAIL_PASSWORD`: Google 账号生成的 **16 位应用专用密码** (删除空格)。
- `MAIL_TO`: 您的接收邮箱。

## 🔍 故障排查 (邮件发送失败)

如果 GitHub Actions 报 `535 Login fail`：
1. **两步验证**：确保 Google 账号已开启 2-Step Verification。
2. **应用密码**：必须使用 16 位 App Password，填入 Secret 时删除所有空格。
3. **YAML 配置**：确保 `.github/workflows/update.yml` 中 `server_port: 465` 且 `secure: true`。

## 📂 仓库结构
- `update_papers.py`: 核心脚本（多专题抓取、翻译、PDF 生成）。
- `frontend/`: 网页展示端（支持多专题切换）。
- `.github/workflows/update.yml`: GitHub Actions 配置文件。

## 🚀 开发者快速推送
使用本地生成的 `./deploy.sh` 脚本一键同步修改到 GitHub。
