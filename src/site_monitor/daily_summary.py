#!/usr/bin/env python3
"""
每日监控汇总 - 运行所有监控脚本并生成汇总报告
由 cron job 调用，stdout 输出会作为微信消息发送
"""
import subprocess
import os
import sys
from datetime import datetime
from .monitor_config import PROJECT_ROOT, runtime_path

SCRIPTS_DIR = PROJECT_ROOT

CHECK_MODULES = [
    "site_monitor.check_github_trending",
    "site_monitor.check_anthropic",
    "site_monitor.check_openai_engineering",
    "site_monitor.check_langchain_blog",
    "site_monitor.check_claude_code",
    "site_monitor.check_copilot_cli",
]

def run_script(module_name):
    """运行监控模块"""
    try:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
        result = subprocess.run(
            [sys.executable, "-m", module_name],
            capture_output=True, text=True, timeout=120,
            cwd=SCRIPTS_DIR,
            env=env,
        )
        if result.returncode != 0:
            print(f"⚠️ {module_name} 执行失败: {result.stderr[:200]}")
        return result.stdout.strip()
    except Exception as e:
        print(f"⚠️ {module_name} 异常: {e}")
        return ""

def read_pending(filename):
    """读取 pending 文件内容"""
    filepath = runtime_path("pending", filename)
    try:
        with open(filepath, 'r') as f:
            return f.read().strip()
    except:
        return ""

def main():
    today = datetime.now().strftime('%Y-%m-%d')

    # 运行所有监控脚本
    for module_name in CHECK_MODULES:
        run_script(module_name)

    # 汇总报告
    print(f"📊 **每日 AI 监控汇总** — {today}\n")

    # GitHub Trending
    trending = read_pending("github_trending_pending.txt")
    if trending:
        print(trending)
        print()

    # Anthropic Engineering
    anthropic = read_pending("anthropic_pending.txt")
    if anthropic:
        print(anthropic)
        print()

    # OpenAI Engineering
    openai = read_pending("openai_engineering_pending.txt")
    if openai:
        print(openai)
        print()

    # LangChain Blog
    langchain = read_pending("langchain_blog_pending.txt")
    if langchain:
        print(langchain)
        print()

    # Claude Code
    claude = read_pending("claude_code_pending.txt")
    if claude:
        print(claude)
        print()

    # Copilot CLI
    copilot = read_pending("copilot_cli_pending.txt")
    if copilot:
        print(copilot)

if __name__ == "__main__":
    main()
