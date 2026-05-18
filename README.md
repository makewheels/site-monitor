# Site Monitor - 网站更新监控

监控多个网站的文章更新，有新文章时自动通知。

## 功能

- 定时检查网站新文章（默认每小时）
- 支持多网站配置
- 第一次运行不通知已有文章
- 新文章通过通知队列发送
- Web UI 查看配置和历史

## 运行

```bash
cd ~/PythonProjects/site_monitor

# 后台运行（无 Web UI）
python3 main.py --no-web &

# 带 Web UI 运行（访问 http://localhost:5000）
python3 main.py
```

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

新文章写入 `runtime/pending/pending_notifications.json`，等待心跳检查时发送飞书消息。

## 开发

监控源统一放在 `config.json` 的 `monitor_sources`。新增 RSSHub、Atom、API、raw changelog 地址时先改这里，再通过 `src/site_monitor/monitor_config.py` 读取。

后处理统一放在 `config.json` 的 `postprocessors`。每个条目指定 `module`、`function` 和 `options`，函数接收 payload dict 并返回 payload dict。Claude Code changelog 当前会按“功能更新”和“修复/其他”拆分。

日报发送统一放在 `config.json` 的 `delivery`。当前 provider 是 `hermes_weixin`，复用本机 Hermes 的微信账号和 token，但由本项目主动调用发送。

运行验证：

```bash
python3 -m json.tool config.json >/dev/null
python3 -m py_compile src/site_monitor/*.py scripts/*.py daily_summary.py main.py notifier.py
python3 -m pytest
```

## Android App 第一版

仓库内新增了一个最小 Android App 工程：`android/`。第一版不做推送，打开 App 后主动从云端 API 拉取最新日报和历史。

本地演示 API 不依赖 MongoDB：

```bash
cd ~/PythonProjects/site_monitor
PYTHONPATH=src python3 -m site_monitor.demo_cloud_api
```

真机测试时让手机访问 Mac 的局域网地址：

```bash
cd ~/PythonProjects/site_monitor
PYTHONPATH=src SITE_MONITOR_DEMO_HOST=0.0.0.0 python3 -m site_monitor.demo_cloud_api
```

Android debug 构建：

```bash
cd ~/PythonProjects/site_monitor/android
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
