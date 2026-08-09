#!/usr/bin/env python3
"""检查 GitHub Trending 每日热门项目"""
import json
import urllib.request
import re
import os
from datetime import datetime
from .monitor_config import runtime_path
from .postprocess import apply_postprocessors

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

MAX_REPOS = 5  # 每天只推送 Top N 个 trending 项目

STATE_FILE = runtime_path("state", "github_trending_state.json")
PENDING_FILE = runtime_path("pending", "github_trending_pending.txt")
PROJECTS_FILE = runtime_path("pending", "github_trending_projects.json")

# 中文化词典（按顺序应用，先匹配先生效）
ZH_DICT = [
    # === 前缀清理 ===
    (r'^A (ML|machine learning) ', r'\1 '),
    (r'^An? ', ''),
    (r'^The ', ''),
    (r'^Open-source ', '开源 '),
    (r'^Open source ', '开源 '),
    (r'^Free ', '免费 '),
    (r'^A ', ''),
    # === 完整短语（优先匹配长短语） ===
    (r'knowledge workers?', '知识工作者'),
    (r'knowledge graphs?', '知识图谱'),
    (r'\bagents?\b', '智能体'),
    (r'\bmodels?\b', '模型'),
    (r'\b(plugins?|plug-?ins?)\b', '插件'),
    (r'fully automatic', '全自动'),
    (r'censorship removal', '审查移除'),
    (r'foundation model', '基础模型'),
    (r'financial market', '金融市场'),
    (r'cyber livings', '数字生命'),
    (r'bring them into our worlds', '带入我们的世界'),
    (r'software development methodology', '软件开发方法论'),
    (r'for the first time ever', '史上首次'),
    (r'in real.?time', '实时'),
    (r'out of the box', '开箱即用'),
    (r'no code', '无代码'),
    (r'low code', '低代码'),
    (r'zero.?shot', '零样本'),
    (r'few.?shot', '少样本'),
    (r'end.?to.?end', '端到端'),
    (r'state.?of.?the.?art', '最先进'),
    (r'human.?in.?the.?loop', '人机协同'),
    (r'retrieval.?augmented generation', '检索增强生成'),
    (r'RAG\s', 'RAG '),
    (r'fine.?tun(e|ing)', '微调'),
    (r'prompt engineering', '提示工程'),
    (r'chain.?of.?thought', '思维链'),
    (r'knowledge base', '知识库'),
    (r'workflow automation', '工作流自动化'),
    (r'structured cybersecurity skills', '结构化网络安全技能'),
    (r'cybersecurity skills', '网络安全技能'),
    (r'mapped to', '覆盖'),
    (r'CSF', 'CSF'),
    (r'AI RMF', 'AI RMF'),
    (r'D3FEND', 'D3FEND'),
    (r'ATT&CK', 'ATT&CK'),
    (r'ATLAS', 'ATLAS'),
    (r'MITRE', 'MITRE'),
    (r'NIST', 'NIST'),
    (r'security frameworks?', '安全框架'),
    (r'container of souls', '灵魂容器'),
    (r'self.?hosted', '自托管'),
    (r'you.?owned', '自有'),
    (r'Grok Companion', 'Grok 伴侣'),
    (r'Neuro.?sama', 'Neuro-sama'),
    (r'agentic skills? framework', '智能体技能框架'),
    (r'skills? framework', '技能框架'),
    (r'primarily intended for', '主要面向'),
    (r'AI tells', 'AI 套话'),
    (r'boring,? generic slop', '无聊通用的废话'),
    (r'gives your AI good taste', '赋予 AI 好品味'),
    (r'good taste', '好品味'),
    (r'stops? the AI from generating', '阻止 AI 生成'),
    (r'turn any code into', '将任意代码转为'),
    (r'interactive knowledge graph', '交互式知识图谱'),
    (r'you can explore', '可探索'),
    (r'ask questions about', '提问'),
    (r'graphs that teach', '用于教学的知识图谱'),
    (r'graphs that impress', '炫技的知识图谱'),
    (r'Agent harness performance optimization', '智能体性能优化系统'),
    (r'performance optimization', '性能优化'),
    (r'research.?first development', '研究优先的开发'),
    (r'structured cybersecurity', '结构化网络安全'),
    (r'curated list', '精选列表'),
    (r'the best free apps', '最佳免费应用'),
    (r'advanced guide', '进阶指南'),
    (r'learning English', '学英语'),
    (r'English level.up', '英语水平提升'),
    (r'language models?', '语言模型'),
    (r'financial markets?', '金融市场'),
    (r'compose, extend.*observe every service', '组合、扩展、观测所有服务'),
    (r'skill file', '技能文件'),
    (r'from prose', '从文章中'),
    (r'Agent harness', '智能体系统'),
    (r'observation platform', '观测平台'),
    (r'designed for AI', '面向 AI 设计'),
    (r'Free Domain For Everyone', '免费域名，人人可用'),
    (r'for PC.*mobile', 'PC 和移动端'),
    (r'effortlessly compose', '轻松组合'),
    # === 工具/库/框架 ===
    (r'framework for', '的框架'),
    (r'library for', '的库'),
    (r'tools? for', '的工具'),
    (r'for (Mac|Windows|Linux|iOS|Android)', r'在\1上'),
    # === 连接词 ===
    (r',? and ', '、'),
    (r',? or ', '或'),
    # === 动作动词 ===
    (r'\buse[sd]?\b', '使用'),
    (r'\bbuild[st]?\b', '构建'),
    (r'\bcreate[sd]?\b', '创建'),
    (r'\brun[sn]?\b', '运行'),
    (r'generat[ei]ng?\s', '生成'),
    (r'generat[ei]on\s', '生成'),
    (r'generat[eo]r\s', '生成器'),
    (r'develop[si]?ng?\s', '开发'),
    (r'deploy[si]?ng?\s', '部署'),
    (r'train[si]?ng?\s', '训练'),
    (r'learn[si]?ng?\s', '学习'),
    (r'hack[si]?ng?\s', '破解'),
    (r'automat[ei]ng?\s', '自动化'),
    (r'monitor[si]?ng?\s', '监控'),
    (r'analyz[ei]ng?\s', '分析'),
    (r'manag[ei]ng?\s', '管理'),
    (r'optimiz[ei]ng?\s', '优化'),
    (r'connect[si]?ng?\s', '连接'),
    (r'access[si]?ng?\s', '访问'),
    (r'download[si]?ng?\s', '下载'),
    (r'shar[ei]ng?\s', '分享'),
    (r'search[si]?ng?\s', '搜索'),
    (r'complet[ei]ng?\s', '完成'),
    (r'enabl[ei]ng?\s', '实现'),
    (r'provid[ei]ng?\s', '提供'),
    (r'support[si]?ng?\s', '支持'),
    (r'convert[si]?ng?\s', '转换'),
    (r'process[si]?ng?\s', '处理'),
    (r'render[si]?ng?\s', '渲染'),
    (r'display[si]?ng?\s', '展示'),
    (r'debug[gsi]?ng?\s', '调试'),
    (r'test[si]?ng?\s', '测试'),
    (r'verif[yi]ng?\s', '验证'),
    (r'replac[ei]ng?\s', '替换'),
    (r'remov[ei]ng?\s', '移除'),
    (r'remov[ea]l\s', '移除'),
    (r'explor[eings]*\s', '探索'),
    (r'observ[ei]ng?\s', '观测'),
    (r'extend[si]?ng?\s', '扩展'),
    (r'achiev[ei]ng?\s', '实现'),
    (r'\bwrite\s', '编写'),
    (r'without restarting', '无需重启'),
    (r're.scan', '重新扫描'),
    # === 概念名词 ===
    (r'AI agent', 'AI 智能体'),
    (r'AI ', 'AI '),
    (r'artificial intelligence', '人工智能'),
    (r'machine learning', '机器学习'),
    (r'large language model', '大语言模型'),
    (r'LLM[s]?\s', 'LLM '),
    (r'LLM-based', '基于LLM的'),
    (r'generative AI', '生成式AI'),
    (r'conversational AI', '对话式AI'),
    (r'neural network', '神经网络'),
    (r'deep learning', '深度学习'),
    (r'NLP\s', 'NLP '),
    (r'natural language processing', '自然语言处理'),
    (r'computer vision', '计算机视觉'),
    (r'reinforcement learning', '强化学习'),
    (r'knowledge workers?', '知识工作者'),
    (r'knowledge graphs?', '知识图谱'),
    (r'\bagents?\b', '智能体'),
    (r'\bmodels?\b', '模型'),
    (r'\b(plugins?|plug-?ins?)\b', '插件'),
    # === 描述词 ===
    (r'\bpowerful\b', '强大'),
    (r'\bsimple\b', '简洁'),
    (r'\bfast\b', '快速'),
    (r'\beasy\b', '简单'),
    (r'\blightweight\b', '轻量'),
    (r'\bmodern\b', '现代化'),
    (r'\bscalable\b', '可扩展'),
    (r'\bsecure\b', '安全'),
    (r'production-ready', '生产就绪'),
    (r'real.?time', '实时'),
    (r'high.?performance', '高性能'),
    (r'cross.?platform', '跨平台'),
    (r'cloud.?native', '云原生'),
    (r'self.?hosted', '自托管'),
    (r'serverless', '无服务器'),
    (r'microservices?', '微服务'),
    (r'restful', 'RESTful'),
    (r'kubernetes?', 'Kubernetes'),
    (r'docker[\s-]', 'Docker '),
    (r'open source', '开源'),
    (r'free and open', '免费开源'),
    (r'minimalist', '极简'),
    (r'blazing fast', '极速'),
    (r'privacy.?focused', '注重隐私'),
    (r'privacy.?first', '隐私优先'),
    (r'fully local', '完全本地'),
    (r'offline', '离线'),
    (r'alternative to', '的替代品'),
    # === 技术名词 ===
    (r'\bAPI[s]?\b', 'API'),
    (r'\bGUI\b', 'GUI'),
    (r'\bCLI\b', 'CLI'),
    (r'\bSDK\b', 'SDK'),
    (r'\bDatabase[s]?\b', '数据库'),
    (r'\bServer[s]?\b', '服务器'),
    (r'\bClient[s]?\b', '客户端'),
    (r'\bWebapp[s]?\b', 'Web应用'),
    (r'\bApp[s]?\b', '应用'),
    (r'\bBot[s]?\b', '机器人'),
    (r'\bChatbot[s]?\b', '聊天机器人'),
    (r'\bPlugin[s]?\b', '插件'),
    (r'\bExtension[s]?\b', '扩展'),
    (r'\bModule[s]?\b', '模块'),
    (r'\bPackage[s]?\b', '包'),
    (r'\bRepository\b', '仓库'),
    (r'repo[s]itory', '仓库'),
    (r'\bDashboard[s]?\b', '仪表盘'),
    (r'\bMonitor[s]?\b', '监控器'),
    (r'\bAnalytics\b', '数据分析'),
    (r'\bBenchmark[s]?\b', '基准测试'),
    (r'\bScript[s]?\b', '脚本'),
    (r'\bTemplate[s]?\b', '模板'),
    (r'\bConfig[s]?\b', '配置'),
    (r'\bParser[s]?\b', '解析器'),
    (r'\bEngine[s]?\b', '引擎'),
    (r'\bRuntime[s]?\b', '运行时'),
    (r'\bcompiler[s]?\b', '编译器'),
    (r'\binterpreter[s]?\b', '解释器'),
    (r'\bcontainer[s]?\b', '容器'),
    (r'\bworkflow[s]?\b', '工作流'),
    (r'\bpipeline[s]?\b', '流水线'),
    (r'\bdeployment[s]?\b', '部署'),
    (r'\binfrastructure\b', '基础设施'),
    (r'\bbrowser\b', '浏览器'),
    (r'\bterminal\b', '终端'),
    (r'\bdesktop\b', '桌面'),
    (r'\bmobile\b', '移动端'),
    (r'\bbackend\b', '后端'),
    (r'\bfrontend\b', '前端'),
    (r'\bfull.?stack\b', '全栈'),
    # === 常见词组 ===
    (r'code generation', '代码生成'),
    (r'code review', '代码审查'),
    (r'image generation', '图像生成'),
    (r'video generation', '视频生成'),
    (r'text to speech', '文本转语音'),
    (r'speech to text', '语音转文本'),
    (r'face recognition', '人脸识别'),
    (r'object detection', '目标检测'),
    (r'sentiment analysis', '情感分析'),
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
    (r'\bdataset\b', '数据集'),
    (r'\bembeddings?\b', '嵌入'),
    (r'vector (database|store|db)', '向量数据库'),
    (r'changelog', '更新日志'),
    (r'\bchangelog\b', '更新日志'),
    (r'documentation', '文档'),
    (r'tutorial', '教程'),
    (r'boilerplate', '模板代码'),
    (r'starter kit', '起步套件'),
    (r'starter template', '起步模板'),
    (r'getting started', '快速上手'),
    (r'\bdemo\b', '演示'),
    (r'\bexample\b', '示例'),
    # === 句尾清理 ===
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


def fetch_trending(url="https://github.com/trending"):
    """获取 GitHub Trending 页面"""
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

    repos = parse_trending(html)[:MAX_REPOS]
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
            f.write("# 🔥 GitHub Trending\n\n")
            f.write(f"{today}\n\n")
            if has_new:
                new_names = set(current_names) - last_repos
                f.write(f"发现 {len(new_names)} 个新项目（共 {len(repos)} 个项目）:\n\n")
            else:
                f.write(f"今日 trending 共 {len(repos)} 个项目:\n\n")

            project_blocks = []
            processed = apply_postprocessors("github_trending", {"repos": repos})
            repos = processed.get("repos", repos)
            with open(PROJECTS_FILE, "w", encoding="utf-8") as projects_file:
                json.dump(
                    {
                        "date": today,
                        "period": "daily",
                        "repos": repos,
                    },
                    projects_file,
                    ensure_ascii=False,
                    indent=2,
                )
            for r in repos:
                desc_en = r.get("description", "")
                desc_zh = r.get("zh_summary") or (zh(desc_en) if desc_en else "")
                is_new = r["full_name"] in new_names if has_new else False
                tag = "🆕 " if is_new else ""
                block = f"**{tag}{r['full_name']}**\n"
                if desc_zh:
                    block += f"  {desc_zh}\n"
                block += f"  🔗 https://github.com/{r['full_name']}\n"
                project_blocks.append(block)
            f.write("\n---\n".join(project_blocks))
            f.write("\n")

        print(f"写入 pending: {len(repos)} 个 trending 项目")
    else:
        state["last_report_date"] = last_report_date
        save_state(state)
        print(f"今日已报过，无新变化。当前 trending 共 {len(repos)} 个")


if __name__ == "__main__":
    main()
