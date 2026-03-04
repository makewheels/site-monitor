import json
import os
import time
import logging
from datetime import datetime
from threading import Thread
from flask import Flask, render_template_string, jsonify, request
import requests
from bs4 import BeautifulSoup
import schedule

CONFIG_FILE = "config.json"
STATE_FILE = "state.json"

app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {"sites": [], "check_interval": 3600}


def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"notified_articles": {}, "last_check": None, "history": [], "initialized": False}


def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def fetch_page(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return None


def parse_articles(html, site_config):
    if not html:
        return []
    
    soup = BeautifulSoup(html, 'html.parser')
    articles = []
    
    article_selector = site_config.get('article_selector', 'article')
    title_selector = site_config.get('title_selector', 'h2, h3')
    link_selector = site_config.get('link_selector', 'a')
    
    article_elements = soup.select(article_selector)
    
    for article_elem in article_elements:
        title_elem = article_elem.select_one(title_selector)
        link_elem = article_elem.select_one(link_selector)
        
        if title_elem:
            title = title_elem.get_text(strip=True)
            link = None
            
            if link_elem and link_elem.get('href'):
                link = link_elem['href']
                if link.startswith('/'):
                    from urllib.parse import urljoin
                    link = urljoin(site_config['url'], link)
                elif not link.startswith('http'):
                    from urllib.parse import urljoin
                    link = urljoin(site_config['url'], link)
            
            if title and link:
                articles.append({
                    'title': title,
                    'link': link,
                    'site': site_config['name']
                })
    
    return articles


def check_site(site_config):
    site_name = site_config['name']
    logger.info(f"Checking site: {site_name}")
    
    html = fetch_page(site_config['url'])
    if not html:
        return []
    
    articles = parse_articles(html, site_config)
    logger.info(f"Found {len(articles)} articles on {site_name}")
    
    return articles


def notify(article):
    """通知新文章 - 写入待发送队列"""
    logger.info(f"NEW ARTICLE: {article['title']}")
    logger.info(f"  URL: {article['link']}")
    logger.info(f"  Site: {article['site']}")
    
    # 写入通知队列
    import notifier
    notifier.add_notification(article)
    
    print(f"🔔 新文章: {article['title']}")


def add_to_history(state, article):
    history_entry = {
        'title': article['title'],
        'link': article['link'],
        'site': article['site'],
        'notified_at': datetime.now().isoformat()
    }
    state['history'].insert(0, history_entry)
    state['history'] = state['history'][:100]


def check_all_sites():
    config = load_config()
    state = load_state()
    is_first_run = not state.get('initialized', False)
    
    for site in config.get('sites', []):
        if not site.get('enabled', True):
            continue
        
        site_name = site['name']
        articles = check_site(site)
        
        if site_name not in state['notified_articles']:
            state['notified_articles'][site_name] = []
        
        notified = state['notified_articles'][site_name]
        new_articles = []
        
        for article in articles:
            article_key = article['link']
            
            if article_key not in notified:
                new_articles.append(article)
                notified.append(article_key)
        
        # 首次运行：发送汇总通知
        if is_first_run and new_articles:
            import notifier
            notifier.add_notification({
                'type': 'summary',
                'site': site_name,
                'count': len(new_articles),
                'articles': new_articles[:5]  # 最多显示5篇
            })
            # 记录到历史
            for article in new_articles[:5]:
                add_to_history(state, article)
        # 后续运行：逐篇通知新文章
        elif not is_first_run and new_articles:
            for article in new_articles:
                notify(article)
                add_to_history(state, article)
    
    state['initialized'] = True
    state['last_check'] = datetime.now().isoformat()
    save_state(state)


def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(1)


def start_scheduler():
    config = load_config()
    interval = config.get('check_interval', 3600)
    
    schedule.every(interval).seconds.do(check_all_sites)
    logger.info(f"Scheduler started, checking every {interval} seconds")
    
    check_all_sites()
    
    schedule_thread = Thread(target=run_schedule, daemon=True)
    schedule_thread.start()


HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Site Monitor</title>
    <meta charset="utf-8">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
        h1 { color: #333; }
        .card { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .card h2 { margin-top: 0; color: #444; }
        .status { display: inline-block; padding: 4px 12px; border-radius: 4px; font-size: 14px; }
        .status.enabled { background: #d4edda; color: #155724; }
        .status.disabled { background: #f8d7da; color: #721c24; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; }
        .nav { margin-bottom: 20px; }
        .nav a { margin-right: 20px; color: #0066cc; text-decoration: none; }
        .nav a:hover { text-decoration: underline; }
        pre { background: #f8f9fa; padding: 15px; border-radius: 4px; overflow-x: auto; }
        .btn { background: #0066cc; color: white; padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; }
        .btn:hover { background: #0052a3; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; font-weight: bold; }
        .form-group input { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
    </style>
</head>
<body>
    <h1>📰 Site Monitor</h1>
    <div class="nav">
        <a href="/">Home</a>
        <a href="/config">Config</a>
        <a href="/history">History</a>
    </div>
    
    <div class="card">
        <h2>Status</h2>
        <p>Last check: {{ last_check }}</p>
        <button class="btn" onclick="checkNow()">Check Now</button>
    </div>
    
    <div class="card">
        <h2>Monitored Sites</h2>
        <table>
            <thead>
                <tr>
                    <th>Name</th>
                    <th>URL</th>
                    <th>Status</th>
                    <th>Articles Notified</th>
                </tr>
            </thead>
            <tbody>
                {% for site in sites %}
                <tr>
                    <td>{{ site.name }}</td>
                    <td><a href="{{ site.url }}" target="_blank">{{ site.url }}</a></td>
                    <td><span class="status {{ 'enabled' if site.enabled else 'disabled' }}">{{ 'Enabled' if site.enabled else 'Disabled' }}</span></td>
                    <td>{{ notified_counts.get(site.name, 0) }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    
    <div class="card">
        <h2>Recent Notifications</h2>
        <table>
            <thead>
                <tr>
                    <th>Time</th>
                    <th>Site</th>
                    <th>Title</th>
                    <th>Link</th>
                </tr>
            </thead>
            <tbody>
                {% for item in history[:10] %}
                <tr>
                    <td>{{ item.notified_at[:19] }}</td>
                    <td>{{ item.site }}</td>
                    <td>{{ item.title }}</td>
                    <td><a href="{{ item.link }}" target="_blank">View</a></td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    
    <script>
        function checkNow() {
            fetch('/check', { method: 'POST' })
                .then(r => r.json())
                .then(d => alert('Check triggered!'))
                .catch(e => alert('Error: ' + e));
        }
    </script>
</body>
</html>
'''

CONFIG_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Config - Site Monitor</title>
    <meta charset="utf-8">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
        h1 { color: #333; }
        .card { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .nav { margin-bottom: 20px; }
        .nav a { margin-right: 20px; color: #0066cc; text-decoration: none; }
        pre { background: #f8f9fa; padding: 15px; border-radius: 4px; overflow-x: auto; }
    </style>
</head>
<body>
    <h1>⚙️ Configuration</h1>
    <div class="nav">
        <a href="/">Home</a>
        <a href="/config">Config</a>
        <a href="/history">History</a>
    </div>
    
    <div class="card">
        <h2>config.json</h2>
        <pre>{{ config_json }}</pre>
    </div>
    
    <div class="card">
        <h2>state.json</h2>
        <pre>{{ state_json }}</pre>
    </div>
</body>
</html>
'''

HISTORY_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>History - Site Monitor</title>
    <meta charset="utf-8">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
        h1 { color: #333; }
        .card { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .nav { margin-bottom: 20px; }
        .nav a { margin-right: 20px; color: #0066cc; text-decoration: none; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; }
    </style>
</head>
<body>
    <h1>📜 History</h1>
    <div class="nav">
        <a href="/">Home</a>
        <a href="/config">Config</a>
        <a href="/history">History</a>
    </div>
    
    <div class="card">
        <table>
            <thead>
                <tr>
                    <th>Time</th>
                    <th>Site</th>
                    <th>Title</th>
                    <th>Link</th>
                </tr>
            </thead>
            <tbody>
                {% for item in history %}
                <tr>
                    <td>{{ item.notified_at[:19] }}</td>
                    <td>{{ item.site }}</td>
                    <td>{{ item.title }}</td>
                    <td><a href="{{ item.link }}" target="_blank">{{ item.link }}</a></td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</body>
</html>
'''


@app.route('/')
def index():
    config = load_config()
    state = load_state()
    
    sites = config.get('sites', [])
    history = state.get('history', [])
    last_check = state.get('last_check', 'Never')
    
    notified_counts = {}
    for site_name, articles in state.get('notified_articles', {}).items():
        notified_counts[site_name] = len(articles)
    
    return render_template_string(HTML_TEMPLATE,
        sites=sites,
        history=history,
        last_check=last_check[:19] if last_check else 'Never',
        notified_counts=notified_counts)


@app.route('/config')
def config_page():
    config = load_config()
    state = load_state()
    
    return render_template_string(CONFIG_TEMPLATE,
        config_json=json.dumps(config, indent=2),
        state_json=json.dumps(state, indent=2))


@app.route('/history')
def history_page():
    state = load_state()
    history = state.get('history', [])
    
    return render_template_string(HISTORY_TEMPLATE, history=history)


@app.route('/check', methods=['POST'])
def trigger_check():
    check_all_sites()
    return jsonify({'status': 'ok'})


@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    if request.method == 'POST':
        config = load_config()
        new_config = request.json
        config.update(new_config)
        save_config(config)
        return jsonify({'status': 'ok'})
    return jsonify(load_config())


@app.route('/api/state')
def api_state():
    return jsonify(load_state())


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--no-web':
        start_scheduler()
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
    else:
        start_scheduler()
        logger.info("Starting web server on http://localhost:5000")
        app.run(host='0.0.0.0', port=5000, debug=False)
