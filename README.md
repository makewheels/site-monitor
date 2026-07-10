# Site Monitor - 网站更新监控

每天汇总 GitHub Trending、AI 厂商博客和工具更新，写入腾讯云轻量服务器里的 MongoDB，并推送到飞书。

## 功能

- 北京时间每天 07:00 自动检查并推送
- 支持多网站配置
- MongoDB 持久化去重状态，避免 CI 重复发送历史文章
- GitHub Trending Top 5 使用大模型生成一句中文介绍
- 飞书开放平台直接投递，不依赖本地常驻进程
- Web UI 查看配置和历史

## 运行

```bash
cd ~/workspace/tools/site_monitor
uv sync

# 手动生成并投递一次日报
uv run python daily_summary.py

# 带 Web UI 运行（访问 http://localhost:5000）
uv run python main.py
```

本地配置复制自 `.env.example`。真实 API Key、Mongo URI、飞书 App Secret、接收人 ID 和服务器地址只能放在 `.env` 或 GitHub Secrets/Variables。

## 配置

编辑 `config.json` 添加网站：

```json
{
  "sites": [
    {
      "name": "网站名称",
      "url": "https://example.com/articles",
      "article_selector": "article",
      "title_selector": "h2, h3",
      "link_selector": "a",
      "enabled": true
    }
  ],
  "check_interval": 3600
}
```

## 文件说明

- `src/site_monitor/` - 主程序和监控实现
- `main.py` / `daily_summary.py` / `notifier.py` - 根目录兼容性入口，实际代码在 `src/site_monitor/`
- `scripts/check_*.py` - 手动运行单个监控的兼容性入口
- `config.json` - 网站配置
- `runtime/state/` - 状态（已通知文章、已见版本等）
- `runtime/pending/` - 待发送/待汇总内容
- `runtime/logs/` - 本地运行日志
- `notifier.py` - 通知模块入口

## 通知方式

`daily_summary.py` 组装日报后，通过飞书开放 API 发送交互卡片。云端需要：

- GitHub Variables：`FEISHU_APP_ID`、`LLM_BASE_URL`、`LLM_MODEL`
- GitHub Secrets：`FEISHU_APP_SECRET`、`FEISHU_USER_ID` 或 `FEISHU_CHAT_ID`、`DASHSCOPE_API_KEY`、`SITE_MONITOR_MONGO_URI`、`SITE_MONITOR_DB_NAME`

生产调度位于 `.github/workflows/daily-monitor.yml`，时区固定为 `Asia/Shanghai`。当前源的更新频率均远低于每天 20 条，日报场景每天抓取一次足够；提高到每小时只会增加请求量，并不会让 07:00 日报更完整。

## 开发

监控源统一放在 `config.json` 的 `monitor_sources`。新增 RSSHub、Atom、API、raw changelog 地址时先改这里，再通过 `src/site_monitor/monitor_config.py` 读取。

后处理统一放在 `config.json` 的 `postprocessors`。每个条目指定 `module`、`function` 和 `options`，函数接收 payload dict 并返回 payload dict。Claude Code changelog 当前会按“功能更新”和“修复/其他”拆分。

日报发送统一放在 `config.json` 的 `delivery`。当前 provider 是 `feishu`；CI 使用飞书 Open API，本机未配置 Open API 凭据时可回退到 `lark-cli`。

运行验证：

```bash
uv run python -m json.tool config.json >/dev/null
uv run python -m py_compile src/site_monitor/*.py scripts/*.py daily_summary.py main.py notifier.py
uv run pytest
```

## Android App 第一版

仓库内新增了一个最小 Android App 工程：`android/`。第一版不做推送，打开 App 后主动从云端 API 拉取最新日报和历史。

本地演示 API 不依赖 MongoDB：

```bash
cd ~/workspace/tools/site_monitor
uv run python -m site_monitor.demo_cloud_api
```

真机测试时让手机访问 Mac 的局域网地址：

```bash
cd ~/workspace/tools/site_monitor
SITE_MONITOR_DEMO_HOST=0.0.0.0 uv run python -m site_monitor.demo_cloud_api
```

Android debug 构建：

```bash
cd ~/workspace/tools/site_monitor/android
ANDROID_HOME=/Users/mint/Library/Android/sdk \
SITE_MONITOR_ANDROID_API_URL=http://10.0.2.2:5001 \
SITE_MONITOR_ANDROID_APP_TOKEN=dev-token \
gradle :app:assembleDebug
```

真机本地测试时把 `SITE_MONITOR_ANDROID_API_URL` 改成 Mac 局域网地址：

```bash
ANDROID_HOME=/Users/mint/Library/Android/sdk \
SITE_MONITOR_ANDROID_API_URL=http://<Mac局域网IP>:5001 \
SITE_MONITOR_ANDROID_APP_TOKEN=dev-token \
gradle :app:assembleDebug
```

生成的 APK 在：

```bash
android/app/build/outputs/apk/debug/app-debug.apk
```

正式云端 API 入口是 `site_monitor.cloud_api:app`，部署模板在 `deploy/`，GitHub Actions workflow 在 `.github/workflows/deploy-tencent-cloud.yml`。正式环境需要在服务器 env 中配置：

```bash
SITE_MONITOR_MONGO_URI=
SITE_MONITOR_DB_NAME=site_monitor
SITE_MONITOR_UPLOAD_TOKEN=
SITE_MONITOR_APP_TOKEN=
```
