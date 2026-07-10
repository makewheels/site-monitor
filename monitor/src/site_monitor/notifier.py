import json
import os
from datetime import datetime
from .monitor_config import runtime_path

NOTIFICATION_FILE = runtime_path("pending", "pending_notifications.json")
TRENDING_HISTORY_FILE = runtime_path("state", "trending_history.json")

def get_trending_history():
    """获取历史 trending 项目"""
    if os.path.exists(TRENDING_HISTORY_FILE):
        with open(TRENDING_HISTORY_FILE, 'r') as f:
            return json.load(f)
    return []

def save_trending_history(projects):
    """保存 trending 项目历史（保留最近 100 个）"""
    with open(TRENDING_HISTORY_FILE, 'w') as f:
        json.dump(projects[-100:], f, indent=2)

def is_new_project(project_name, history):
    """判断是否是新项目"""
    return project_name not in history

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
    # GitHub Trending 每日汇总
    elif article.get('type') == 'trending':
        notifications.append({
            'type': 'trending',
            'site': article['site'],
            'count': article['count'],
            'articles': article['articles'],
            'date': article.get('date'),
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
    # GitHub Trending 每日汇总
    if notification.get('type') == 'trending':
        articles = notification.get('articles', [])
        date = notification.get('date', '')
        
        # 只取前 5 个
        top5 = articles[:5]
        
        # 获取历史记录，判断哪些是新项目
        history = get_trending_history()
        new_projects = []
        
        lines = [f"🔥 **GitHub Trending** ({date})\n"]
        lines.append("今日 Top 5 热门项目：\n")
        
        for i, article in enumerate(top5, 1):
            title = article['title']
            link = article['link']
            desc = article.get('description', '')
            
            # 简化描述：最多 60 字符
            if desc:
                desc = desc[:60] + '...' if len(desc) > 60 else desc
            else:
                desc = '暂无描述'
            
            # 提取项目名
            project_name = title.strip()
            
            # 判断是否新项目
            is_new = is_new_project(project_name, history)
            new_marker = " 🆕" if is_new else ""
            
            lines.append(f"**{i}. {project_name}**{new_marker}")
            lines.append(f"   {desc}")
            lines.append(f"   [GitHub]({link})\n")
            
            if is_new:
                new_projects.append(project_name)
        
        # 更新历史
        all_projects = history + [a['title'].strip() for a in top5]
        save_trending_history(list(set(all_projects)))
        
        # 如果有新项目，加个提示
        if new_projects:
            lines.append(f"💡 {len(new_projects)} 个新上榜项目")
        
        return '\n'.join(lines)
    
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
