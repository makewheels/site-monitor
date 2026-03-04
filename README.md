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
cd ~/PycharmProjects/site_monitor

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

- `main.py` - 主程序
- `config.json` - 网站配置
- `state.json` - 状态（已通知文章）
- `pending_notifications.json` - 待发送通知队列
- `notifier.py` - 通知模块

## 通知方式

新文章写入 `pending_notifications.json`，等待心跳检查时发送飞书消息。
