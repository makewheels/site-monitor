from site_monitor.daily_summary import daily_delivery_payload


def test_trending_delivery_every_two_days_across_month_boundary():
    trending = {"topic": "github_trending", "status": "content", "body": "trending"}
    other = {"topic": "anthropic_engineering", "status": "content", "body": "article"}
    payload = {"date": "2026-11-30", "items": [trending, other]}

    assert daily_delivery_payload(payload) is payload
    payload["date"] = "2026-12-01"
    filtered = daily_delivery_payload(payload)
    assert filtered["items"] == [other]
    assert filtered["item_count"] == 1
    assert filtered["full_text"].endswith("article")
    assert "trending" not in filtered["full_text"]
    assert payload["items"] == [trending, other]

    other["status"] = "no_update"
    assert daily_delivery_payload(payload) is None
    payload["date"] = "2026-12-02"
    assert daily_delivery_payload(payload) is payload
