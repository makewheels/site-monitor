#!/usr/bin/env python3
"""检查 GitHub Trending 每日热门项目"""
import json
import urllib.request
import re
import os
from datetime import datetime
from .monitor_config import runtime_path

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

STATE_FILE = runtime_path("state", "github_trending_state.json")
PENDING_FILE = runtime_path("pending", "github_trending_pending.txt")

# 中文化词典
ZH_DICT = [
    # 工具类前缀
    (r'^A (ML|machine learning) ', r'\1 '),
    (r'^An? ', ''),
    (r'^The ', ''),
    (r'^Open-source ', '开源 '),
    (r'^Open source ', '开源 '),
    (r'^Free ', '免费 '),
    (r'^A ', ''),
    # 工具/库/框架
    (r'framework for', '的框架'),
    (r'library for', '的库'),
    (r'tool for', '的工具'),
    (r'tools for', '的工具'),
    (r'for (Mac|Windows|Linux|iOS|Android)', r'在\1上'),
    # 动作
    (r'and ', '、'),
    (r'use[d]? ', '使用'),
    (r'build[s]? ', '构建'),
    (r'create[sd]? ', '创建'),
    (r'run[s]? ', '运行'),
    (r'generat[ei]ng?\s', '生成'),
    (r'generat[ei]on\s', '生成'),
    (r'generat[eo]r\s', '生成器'),
    (r'develop[sd]?\s', '开发'),
    (r'developing\s', '开发'),
    (r'deploy[s]? ', '部署'),
    (r'train[s]? ', '训练'),
    (r'learn[s]? ', '学习'),
    (r'build[s]?\s', '构建'),
    (r'hack[s]? ', '黑客'),
    (r'automat(e|ion|ing)\s', '自动化'),
    (r'monitor[s]? ', '监控'),
    (r'analyze[s]? ', '分析'),
    (r'manage[s]? ', '管理'),
    (r'opitimiz(e|ation)\s', '优化'),
    (r'connect[s]? ', '连接'),
    (r'access\s', '访问'),
    (r'download[s]? ', '下载'),
    (r'share[s]? ', '分享'),
    (r'search[s]? ', '搜索'),
    (r'complet[ei]ng?\s', '完成'),
    (r'enabl(e|ing|es)\s', '实现'),
    (r'provid(e|ing|es)\s', '提供'),
    (r'support[s]? ', '支持'),
    (r'convert[s]? ', '转换'),
    (r'process(es|ing)?\s', '处理'),
    (r'render[s]? ', '渲染'),
    (r'display[s]? ', '展示'),
    (r'debug[gs]?\s', '调试'),
    (r'test[s]? ', '测试'),
    (r'verify[s]? ', '验证'),
    (r'replac(e|es|ing)\s', '替换'),
    (r'direct[ly]?\s', ''),
    # AI/ML
    (r'AI ', 'AI '),
    (r'artificial intelligence', '人工智能'),
    (r'machine learning', '机器学习'),
    (r'large language model', '大语言模型'),
    (r'LLM[s]?\s', 'LLM '),
    (r'LLM-based', '基于LLM'),
    (r'generative AI', '生成式AI'),
    (r'conversational AI', '对话式AI'),
    (r'neural network', '神经网络'),
    (r'deep learning', '深度学习'),
    (r'NLP ', 'NLP '),
    (r'natural language processing', '自然语言处理'),
    (r'computer vision', '计算机视觉'),
    (r'reinforcement learning', '强化学习'),
    (r'transformer[s]? ', 'Transformer '),
    (r'agent[s]? ', 'Agent '),
    (r'agents for', '的Agent'),
    # 描述词
    (r'powerful', '强大'),
    (r'simple', '简洁'),
    (r'fast', '快速'),
    (r'easy', '简单'),
    (r'lightweight', '轻量'),
    (r'modern', '现代化'),
    (r'scalable', '可扩展'),
    (r'secure', '安全'),
    (r'production-ready', '生产可用'),
    (r'real-time', '实时'),
    (r'high-performance', '高性能'),
    (r'cross-platform', '跨平台'),
    (r'cloud-native', '云原生'),
    (r'self-hosted', '自托管'),
    (r'serverless', '无服务器'),
    (r'microservices?', '微服务'),
    (r'restful', 'RESTful'),
    (r'kubernetes?', 'Kubernetes'),
    (r'docker[\s-]', 'Docker '),
    # 名词
    (r'API[s]?\s', 'API '),
    (r'GUI\s', 'GUI '),
    (r'CLI\s', 'CLI '),
    (r'SDK\s', 'SDK '),
    (r'DB\s', '数据库'),
    (r'Database[s]? ', '数据库 '),
    (r'Server[s]? ', '服务器 '),
    (r'Client[s]? ', '客户端 '),
    (r'Web ', 'Web '),
    (r'Webapp[s]? ', 'Web应用 '),
    (r'App[s]? ', '应用 '),
    (r'Bot[s]? ', '机器人 '),
    (r'Chatbot[s]? ', '聊天机器人 '),
    (r'Plugin[s]? ', '插件 '),
    (r'Extension[s]? ', '扩展 '),
    (r'Module[s]? ', '模块 '),
    (r'Package[s]? ', '包 '),
    (r'Repository', '仓库'),
    (r'repo[s]itory', '仓库'),
    (r'Dashboard[s]? ', '仪表盘 '),
    (r'Monitor[s]? ', '监控 '),
    (r'Analytics ', '分析 '),
    (r'Benchmark[s]? ', '基准测试 '),
    (r'Script[s]? ', '脚本 '),
    (r'Template[s]? ', '模板 '),
    (r'Config[s]? ', '配置 '),
    (r'Parser[s]? ', '解析器 '),
    (r'Engine[s]? ', '引擎 '),
    (r'Runtime[s]? ', '运行时 '),
    (r'compiler[s]? ', '编译器 '),
    (r'interpreter[s]? ', '解释器 '),
    # 常见trending词组
    (r'(\w+) models?', r'\1模型'),
    (r'(\w+) agents?', r'\1智能体'),
    (r'coding (\w+)', r'\1编程'),
    (r'code generation', '代码生成'),
    (r'code review', '代码审查'),
    (r'image generation', '图像生成'),
    (r'video generation', '视频生成'),
    (r'text to speech', '文本转语音'),
    (r'speech to text', '语音转文本'),
    (r'face recognition', '人脸识别'),
    (r'object detection', '目标检测'),
    (r'sentiment analysis', '情感分析'),
    (r'translation', '翻译'),
    (r'text generation', '文本生成'),
    (r'chat application', '聊天应用'),
    (r'command line', '命令行'),
    (r'file transfer', '文件传输'),
    (r'network scanning', '网络扫描'),
    (r'vulnerability scanning', '漏洞扫描'),
    (r'penetration testing', '渗透测试'),
    (r'security auditing', '安全审计'),
    (r'type checking', '类型检查'),
    (r'static analysis', '静态分析'),
    (r'dynamic analysis', '动态分析'),
    # 句尾清理
    (r'\s*[-|]\s*https?://\S+', ''),
    (r'\s*Build software better, together.*', ''),
    (r'\s*Contribute to .*', ''),
]

def zh(desc):
    """简单规则翻译"""
    if not desc:
        return ""
    desc = re.sub(r'\s*Build software better, together.*', '', desc)
    desc = re.sub(r'\s*Contribute to .*', '', desc)
    desc = re.sub(r'\s*\(https?://\S+\)', '', desc)

    for pattern, repl in ZH_DICT:
        desc = re.sub(pattern, repl, desc, flags=re.IGNORECASE)

    desc = re.sub(r'\s+', ' ', desc).strip()
    desc = re.sub(r'^(一个?|这个|开源|免费|强大|快速|简单)的?\s*', r'\1', desc)
    return desc


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"last_repos": [], "last_check": None, "last_report_date": None}


def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def fetch_trending():
    """获取 GitHub Trending 页面"""
    url = "https://github.com/trending"

    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'text/html'
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode('utf-8')
    except Exception as e:
        print(f"获取失败: {e}")
        return None


def parse_trending(html):
    """使用 BeautifulSoup 精确解析 trending 页面中的仓库列表"""
    repos = []

    if BeautifulSoup:
        soup = BeautifulSoup(html, 'html.parser')
        # 文章列表通常包含在 <article class="Box-row"> 中
        article_rows = soup.find_all('article', class_='Box-row')
        for article in article_rows:
            # 找标题链接: h2 > a
            h2 = article.find('h2')
            if not h2:
                continue
            a = h2.find('a')
            if not a or not a.get('href'):
                continue
            href = a['href'].strip()
            # href 格式: /owner/repo
            if href.count('/') != 2:
                continue
            full_name = href.lstrip('/')
            # 找描述
            desc = ""
            p = article.find('p')
            if p:
                desc = p.get_text(strip=True)[:150]

            repos.append({
                "full_name": full_name,
                "url": f"https://github.com/{full_name}",
                "description": desc
            })

            if len(repos) >= 25:
                break

    if not repos:
        # 回退到正则方式
        print("BeautifulSoup 未找到文章行，回退到正则解析")
        pattern = r'href="(/([a-zA-Z0-9_-]+)/([a-zA-Z0-9._-]+))"'
        all_matches = re.findall(pattern, html)

        seen = set()
        for full_path, owner, name in all_matches:
            if full_path in seen:
                continue
            if full_path.startswith('/sponsors') or full_path.startswith('/apps'):
                continue
            if full_path in ['/trending/developers', '/trending']:
                continue
            seen.add(full_path)
            repos.append({
                "full_name": full_path[1:],
                "url": f"https://github.com{full_path}",
                "description": ""
            })
            if len(repos) >= 25:
                break

    return repos


def fetch_repo_description(owner, repo):
    """获取仓库描述"""
    url = f"https://github.com/{owner}/{repo}"
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8')
            m = re.search(r'<meta name="description" content="([^"]+)"', html)
            if m:
                return m.group(1)[:150]
            m = re.search(r'class="[^"]*f4[^"]*"[^>]*>([^<]+)', html)
            if m:
                return m.group(1).strip()[:150]
    except:
        pass
    return ""


def main():
    state = load_state()
    last_repos = set(state.get("last_repos", []))
    last_report_date = state.get("last_report_date")

    html = fetch_trending()
    if not html:
        return

    repos = parse_trending(html)
    current_names = [r["full_name"] for r in repos]

    today = datetime.now().strftime("%Y-%m-%d")

    # 每天必报一次，不论新旧
    # 如果今天还没报过，或者今天已经报过但有新变化，就写 pending
    report_today_already = (last_report_date == today)
    has_new = bool(set(current_names) - last_repos)

    should_report = (not report_today_already) or has_new

    state["last_repos"] = current_names
    state["last_check"] = datetime.now().isoformat()

    if should_report:
        # 拉取描述（只拉今天新增或首次的，节约请求）
        for r in repos:
            if not r["description"]:
                parts = r["full_name"].split("/")
                if len(parts) == 2:
                    r["description"] = fetch_repo_description(parts[0], parts[1])

        state["last_report_date"] = today
        save_state(state)

        with open(PENDING_FILE, 'w') as f:
            f.write(f"## {today} GitHub Trending\n\n")
            if has_new:
                new_names = set(current_names) - last_repos
                f.write(f"发现 {len(new_names)} 个新项目（共 {len(repos)} 个项目）:\n\n")
            else:
                f.write(f"今日 trending 共 {len(repos)} 个项目:\n\n")

            for r in repos:
                desc_en = r.get("description", "")
                desc_zh = zh(desc_en) if desc_en else ""
                if desc_zh:
                    f.write(f"- **{r['full_name']}** — {desc_zh}\n")
                else:
                    f.write(f"- **{r['full_name']}**\n")
                f.write(f"  https://github.com/{r['full_name']}\n")

        print(f"写入 pending: {len(repos)} 个 trending 项目")
    else:
        state["last_report_date"] = last_report_date
        save_state(state)
        print(f"今日已报过，无新变化。当前 trending 共 {len(repos)} 个")


if __name__ == "__main__":
    main()
