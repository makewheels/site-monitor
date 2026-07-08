#!/usr/bin/env python3
"""
每日监控汇总 - 运行所有监控脚本并生成汇总报告
由 cron job 调用；本程序会按 config.json 的 delivery 配置发送微信消息
"""
import subprocess
import os
import sys
from datetime import datetime
from .monitor_config import PROJECT_ROOT, runtime_path
from .delivery import is_enabled, send_report
from .report_payload import TOPICS, build_payload

SCRIPTS_DIR = PROJECT_ROOT

CHECK_MODULES = [
    "site_monitor.check_github_trending",
    "site_monitor.check_anthropic",
    "site_monitor.check_rss_feeds",
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

def build_report_payload():
    today = datetime.now().strftime('%Y-%m-%d')

    # 运行所有监控脚本
    for module_name in CHECK_MODULES:
        run_script(module_name)

    sections = {
        topic.key: read_pending(topic.pending_file)
        for topic in TOPICS
    }
    return build_payload(sections, date=today)


def build_report():
    return build_report_payload()["full_text"]

def main():
    payload = build_report_payload()
    report = payload["full_text"]
    print(report)
    if is_enabled():
        try:
            result = send_report(report, payload=payload)
            if result.get("skipped"):
                print(f"\n发送跳过: {result.get('reason')}", file=sys.stderr)
            else:
                print("\n微信发送成功", file=sys.stderr)
        except Exception as e:
            print(f"\n⚠️ 发送失败: {e}", file=sys.stderr)
            # Don't crash — cron system will handle delivery as fallback

if __name__ == "__main__":
    main()
