#!/usr/bin/env python3
"""
每日监控汇总 - 运行所有监控脚本并生成汇总报告
由 GitHub Actions 调用；本程序会按 config.json 的 delivery 配置发送飞书消息
"""
import subprocess
import os
import sys
from datetime import datetime
from pathlib import Path

from .article_enrichment import enrich_report_payload
from .monitor_config import PROJECT_ROOT, runtime_dir, runtime_path
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
    state_directory = runtime_dir("state")
    state_snapshot = {
        path.name: path.read_bytes()
        for path in state_directory.glob("*.json")
    }

    for topic in TOPICS:
        Path(runtime_path("pending", topic.pending_file)).unlink(missing_ok=True)

    # 运行所有监控脚本
    for module_name in CHECK_MODULES:
        run_script(module_name)

    sections = {
        topic.key: read_pending(topic.pending_file)
        for topic in TOPICS
    }
    payload = build_payload(sections, date=today)
    try:
        payload = enrich_report_payload(payload)
    except Exception:
        for path in state_directory.glob("*.json"):
            path.unlink(missing_ok=True)
        for filename, content in state_snapshot.items():
            (state_directory / filename).write_bytes(content)
        raise
    metadata = payload.get("ai_enrichment", {})
    print(
        "AI 摘要翻译: "
        f"status={metadata.get('status', 'disabled')} "
        f"articles={metadata.get('enriched_count', 0)}/{metadata.get('requested_count', 0)} "
        f"model={metadata.get('model', '-')}",
        file=sys.stderr,
    )
    return payload


def build_report():
    return build_report_payload()["full_text"]

def main():
    store = None
    mongo_uri = os.environ.get("SITE_MONITOR_MONGO_URI")
    if mongo_uri:
        from .mongo_store import create_store

        store = create_store(
            mongo_uri,
            os.environ.get("SITE_MONITOR_DB_NAME", "site_monitor"),
        )
        restored = store.restore_monitor_state(runtime_dir("state"))
        print(f"MongoDB 状态恢复完成: files={restored}", file=sys.stderr)

    payload = build_report_payload()
    report = payload["full_text"]
    print(report)

    errors = []
    if store is not None:
        try:
            saved = store.save_monitor_state(runtime_dir("state"))
            result = store.upsert_report(payload)
            print(
                f"\n📦 MongoDB 写入成功: report_id={result.get('report_id')} "
                f"items={result.get('item_count')} state_files={saved}",
                file=sys.stderr,
            )
        except Exception as e:
            print(f"\n⚠️ MongoDB 写入失败: {e}", file=sys.stderr)
            errors.append(f"MongoDB: {e}")

    if is_enabled():
        try:
            result = send_report(report, payload=payload)
            if result.get("skipped"):
                print(f"\n发送跳过: {result.get('reason')}", file=sys.stderr)
            elif not result.get("success", False):
                errors.append(f"delivery: {result}")
            else:
                provider = result.get("provider", "未知")
                print(f"\n发送成功 ({provider})", file=sys.stderr)
        except Exception as e:
            print(f"\n⚠️ 发送失败: {e}", file=sys.stderr)
            errors.append(f"delivery: {e}")

    if errors:
        raise RuntimeError("; ".join(errors))

if __name__ == "__main__":
    main()
