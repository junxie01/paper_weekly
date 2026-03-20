# 🧊 冰川地震学论文周报系统 (Hexo 集成版)

一个自动追踪 arXiv 冰川地震学相关论文并自动翻译、分析的系统。

## 🌐 站点集成说明

由于您的主站位于 `junxie01.github.io`，建议采用以下集成方式：

### 1. 部署为子站点 (推荐)
1. 在本仓库的 **Settings > Pages** 中开启部署，选择 `main` 分支。
2. 您的论文页面将自动出现在：`https://www.seis-jun.xyz/cryoseismology_papers/frontend/`
3. 在 Hexo 的 `_config.yml` 菜单中添加该链接即可。

### 2. 自动化流程
- **定时触发**：每周日北京时间上午 8:00 自动运行。
- **手动触发**：在 GitHub Actions 页面点击 "Run workflow"。

## 🛠️ 必须完成的配置 (Secrets)

在 GitHub 仓库 **Settings > Secrets and variables > Actions** 中添加：
- `MAIL_USERNAME`: 您的发送邮箱 (如 QQ 邮箱)。
- `MAIL_PASSWORD`: 邮箱 SMTP 授权码。
- `MAIL_TO`: 您的接收邮箱。

## 📂 仓库结构
- `update_papers.py`: 抓取与翻译脚本。
- `frontend/`: 网页展示端。
- `.github/workflows/update.yml`: 自动化指挥部。

## 🚀 开发者快速推送
使用本地生成的 `./deploy.sh` 脚本一键同步修改到 GitHub。
