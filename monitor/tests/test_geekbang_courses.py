import json

from site_monitor import check_geekbang_courses as collector
from site_monitor.report_payload import build_payload


def test_baseline_new_course_and_delivery_ack(monkeypatch, tmp_path):
    monkeypatch.setenv("SITE_MONITOR_RUNTIME_DIR", str(tmp_path))
    courses = {101: {"id": 101, "title": "既有课程", "type": "c1"}}
    monkeypatch.setattr(collector, "fetch_courses", lambda config: courses)
    state = tmp_path / "state" / collector.STATE_FILE
    report = tmp_path / "pending" / collector.PENDING_REPORT

    collector.main()
    assert json.loads(state.read_text()) == [101]
    assert not report.exists()

    courses.clear()
    courses[102] = {"id": 102, "title": "新课 [视频]", "type": "c3"}
    collector.main()
    payload = build_payload({collector.TOPIC: report.read_text()})
    entry, = payload["items"][0]["entries"]
    assert entry["title"] == "新课 ［视频］"
    assert entry["url"] == "https://time.geekbang.org/course/intro/102"
    assert json.loads(state.read_text()) == [101]
    assert collector.acknowledge_delivery()
    assert json.loads(state.read_text()) == [101, 102]
    report.unlink()
    collector.main()
    assert not report.exists()
