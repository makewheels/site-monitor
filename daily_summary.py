#!/usr/bin/env python3
"""
每日监控汇总 - 运行所有监控脚本并生成汇总报告
"""
import subprocess
import os
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser("~/PythonProjects/site_monitor")

def run_script(script_name):
    """运行监控脚本并返回输出"""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    try:
        result = subprocess.run(
            ["python3", script_path],
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.stdout.strip()
    except Exception as e:
        return f"执行失败: {e}"

def read_pending(filename):
    """读取 pending 文件内容"""
    filepath = os.path.join(SCRIPTS_DIR, filename)
    try:
        with open(filepath, 'r') as f:
            return f.read()
    except:
        return "无数据"

def main():
    # 运行三个监控脚本
    print("=== 运行监控脚本 ===")
    run_script("check_anthropic.py")
    run_script("check_github_trending.py")
    run_script("check_copilot_cli.py")
    
    # 读取汇报内容
    print("\n=== 汇总报告 ===")
    print(f"## {datetime.now().strftime('%Y-%m-%d')} 监控汇总\n")
    
    trending = read_pending("github_trending_pending.txt")
    print(trending)
    print()
    
    anthropic = read_pending("anthropic_pending.txt")
    print(anthropic)
    print()
    
    copilot = read_pending("copilot_cli_pending.txt")
    print(copilot)

if __name__ == "__main__":
    main()
