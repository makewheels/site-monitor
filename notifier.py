import json
import os
from datetime import datetime

NOTIFICATION_FILE = "pending_notifications.json"

def add_notification(article):
    """添加待发送的通知"""
    notifications = []
    if os.path.exists(NOTIFICATION_FILE):
        with open(NOTIFICATION_FILE, 'r') as f:
            notifications = json.load(f)
    
    # 支持汇总通知
    if article.get('type') == 'summary':
        notifications.append({
            'type': 'summary',
            'site': article['site'],
            'count': article['count'],
            'articles': article['articles'],
            'time': datetime.now().isoformat(),
            'sent': False
        })
    else:
        notifications.append({
            'title': article['title'],
            'link': article['link'],
            'site': article['site'],
            'time': datetime.now().isoformat(),
            'sent': False
        })
    
    with open(NOTIFICATION_FILE, 'w') as f:
        json.dump(notifications, f, indent=2, ensure_ascii=False)

def get_pending_notifications():
    """获取待发送的通知"""
    if not os.path.exists(NOTIFICATION_FILE):
        return []
    with open(NOTIFICATION_FILE, 'r') as f:
        return [n for n in json.load(f) if not n.get('sent')]

def mark_all_sent():
    """标记所有通知已发送"""
    if not os.path.exists(NOTIFICATION_FILE):
        return
    with open(NOTIFICATION_FILE, 'r') as f:
        notifications = json.load(f)
    for n in notifications:
        n['sent'] = True
    with open(NOTIFICATION_FILE, 'w') as f:
        json.dump(notifications, f, indent=2, ensure_ascii=False)

def format_notification(notification):
    """格式化通知消息"""
    # 汇总通知
    if notification.get('type') == 'summary':
        site = notification['site']
        count = notification['count']
        articles = notification.get('articles', [])
        lines = [f"📰 **{site}** 监控已启动，当前追踪 {count} 篇文章\n"]
        lines.append("最新文章：")
        for i, article in enumerate(articles[:5], 1):
            lines.append(f"{i}. [{article['title']}]({article['link']})")
        return '\n'.join(lines)
    
    # 单篇通知
    return f"📰 **{notification['site']}** 新文章：\n[{notification['title']}]({notification['link']})"

if __name__ == '__main__':
    # 测试
    add_notification({
        'title': '测试文章',
        'link': 'https://example.com',
        'site': '测试站点'
    })
    print("测试通知已添加")
