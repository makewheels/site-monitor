"""Watch the public Geekbang AI curriculum catalog."""
import json
from pathlib import Path
from time import sleep

import requests

from .monitor_config import get_monitor_source, runtime_path

TOPIC = "geekbang_ai_courses"
PENDING_REPORT = "geekbang_ai_courses_pending.txt"
PENDING_IDS = "geekbang_ai_courses_pending.json"
STATE_FILE = "geekbang_ai_courses.json"
STATE_PATH = Path(__file__).resolve().parents[2] / "data" / STATE_FILE
VIDEO_TYPES = {"c3", "c6", "x50"}


def fetch_courses(config):
    courses = {}
    cursor = 0
    visited = {cursor}
    with requests.Session() as session:
        session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": config["catalog_url"]})
        while True:
            response = session.post(
                config["api_url"],
                json={
                    "tag_ids": [config["tag_id"]],
                    "product_type": config["product_type"],
                    "product_form": 0,
                    "pvip": 0,
                    "prev": cursor,
                    "size": 20,
                    "sort": 1,
                    "with_articles": False,
                },
                timeout=15,
            )
            response.raise_for_status()
            result = response.json()
            if result["code"] != 0:
                raise RuntimeError(f"Geekbang catalog returned code {result['code']}")

            page = result["data"]
            for course in page["products"]:
                courses[course["id"]] = course
            if not page["page"]["more"]:
                if not courses:
                    raise RuntimeError("Geekbang catalog returned no visible courses")
                return courses

            cursor = page["list"][-1]["score"]
            if cursor in visited:
                raise RuntimeError("Geekbang catalog repeated a pagination cursor")
            visited.add(cursor)
            sleep(0.4)


def acknowledge_delivery():
    pending = Path(runtime_path("pending", PENDING_IDS))
    if pending.exists():
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        pending.replace(STATE_PATH)
        return True
    return False


def main():
    config = get_monitor_source(TOPIC)
    courses = fetch_courses(config)
    if not STATE_PATH.exists():
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(
            json.dumps(sorted(courses), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"极客时间体系课基线已建立（{len(courses)} 门）")
        return

    known_ids = set(json.loads(STATE_PATH.read_text(encoding="utf-8")))
    new_courses = [course for course_id, course in courses.items() if course_id not in known_ids]
    if not new_courses:
        print(f"极客时间体系课无更新（核对 {len(courses)} 门）")
        return

    lines = ["## 极客时间人工智能体系课", f"发现 {len(new_courses)} 门新课"]
    for course in new_courses:
        title = " ".join(course["title"].split()).replace("[", "［").replace("]", "］")
        course_path = "course" if course["type"] in VIDEO_TYPES else "column"
        url = config["course_base_url"].format(course_path=course_path, course_id=course["id"])
        lines.extend(["", f"- [{title}]({url})"])
    Path(runtime_path("pending", PENDING_IDS)).write_text(
        json.dumps(sorted(known_ids | courses.keys()), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    Path(runtime_path("pending", PENDING_REPORT)).write_text("\n".join(lines), encoding="utf-8")
    print(f"极客时间体系课发现 {len(new_courses)} 门新课")


if __name__ == "__main__":
    main()
