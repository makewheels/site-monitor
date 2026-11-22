#!/usr/bin/env python3
"""
每日监控汇总 - 运行所有监控脚本并生成汇总报告
由 GitHub Actions 调用；本程序会按 config.json 的 delivery 配置发送飞书消息
"""
import json
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

from .article_enrichment import enrich_report_payload
from .check_geekbang_courses import PENDING_IDS, TOPIC as GEEKBANG_TOPIC, acknowledge_delivery
from .monitor_config import PROJECT_ROOT, runtime_dir, runtime_path
from .delivery import is_enabled, send_report
from .report_payload import TOPICS, attach_trending_projects, build_payload

SCRIPTS_DIR = PROJECT_ROOT
TRENDING_PUSH_START = date(2026, 11, 22)

CHECK_MODULES = [
    "site_monitor.check_github_trending",
    "site_monitor.check_anthropic",
    "site_monitor.check_geekbang_courses",
]

SCRIPT_TIMEOUTS = {
    "site_monitor.check_github_trending": 420,
}


def run_script(module_name):
    """运行监控模块"""
    try:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
        result = subprocess.run(
            [sys.executable, "-m", module_name],
            capture_output=True,
            text=True,
            timeout=SCRIPT_TIMEOUTS.get(module_name, 120),
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
    Path(runtime_path("pending", PENDING_IDS)).unlink(missing_ok=True)
    projects_file = Path(runtime_path("pending", "github_trending_projects.json"))
    projects_file.unlink(missing_ok=True)

    # 运行所有监控脚本
    for module_name in CHECK_MODULES:
        output = run_script(module_name)
        if module_name == "site_monitor.check_geekbang_courses" and output:
            print(output, file=sys.stderr)

    sections = {
        topic.key: read_pending(topic.pending_file)
        for topic in TOPICS
    }
    payload = build_payload(sections, date=today)
    if projects_file.exists():
        try:
            projects_data = json.loads(projects_file.read_text(encoding="utf-8"))
            payload = attach_trending_projects(payload, projects_data.get("repos") or [])
        except (OSError, json.JSONDecodeError):
            pass
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

def daily_delivery_payload(payload):
    report_date = date.fromisoformat(payload["date"])
    if (report_date - TRENDING_PUSH_START).days % 2 == 0:
        return payload

    items = [item for item in payload["items"] if item["topic"] != "github_trending"]
    if not any(item["status"] != "no_update" for item in items):
        return None

    heading = f'📊 **每日 AI 监控汇总** — {payload["date"]}'
    full_text = "\n\n".join([heading, *(item["body"] for item in items)])
    return {**payload, "items": items, "item_count": len(items), "full_text": full_text}


def main():
    from .json_store import create_store

    store = create_store()
    restored = store.restore_monitor_state(runtime_dir("state"))
    print(f"JSON 状态恢复完成: files={restored}", file=sys.stderr)

    payload = build_report_payload()
    report = payload["full_text"]
    print(report)

    errors = []
    try:
            saved = store.save_monitor_state(runtime_dir("state"))
            result = store.upsert_report(payload)
            print(
                f"\n📦 JSON 数据更新完成: report_id={result.get('report_id')} "
                f"items={result.get('item_count')} state_files={saved}",
                file=sys.stderr,
            )
except Exception as e:
        print(f"\n⚠️ JSON 数据写入失败: {e}", file=sys.stderr)
        errors.append(f"JSON: {e}")

    if is_enabled():
        try:
            delivery_payload = daily_delivery_payload(payload)
            if delivery_payload is None:
                result = {"skipped": True, "reason": "trending_off_day"}
            else:
                result = send_report(delivery_payload["full_text"], payload=delivery_payload)
            if result.get("skipped"):
                print(f"\n发送跳过: {result.get('reason')}", file=sys.stderr)
            elif not result.get("success", False):
                errors.append(f"delivery: {result}")
            else:
                provider = result.get("provider", "未知")
                if any(item["topic"] == GEEKBANG_TOPIC for item in delivery_payload["items"]):
                    acknowledge_delivery()
                print(f"\n发送成功 ({provider})", file=sys.stderr)
        except Exception as e:
            print(f"\n⚠️ 发送失败: {e}", file=sys.stderr)
            errors.append(f"delivery: {e}")

    if errors:
        raise RuntimeError("; ".join(errors))

if __name__ == "__main__":
    main()
