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

运行验证：

```bash
python3 -m json.tool config.json >/dev/null
python3 -m py_compile src/site_monitor/*.py scripts/*.py daily_summary.py main.py notifier.py
python3 -m pytest
```
