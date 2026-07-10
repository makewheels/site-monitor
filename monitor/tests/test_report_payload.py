from site_monitor.report_payload import build_payload, extract_entries, extract_links


def test_build_payload_groups_pending_sections_by_topic():
    payload = build_payload(
        {
            "claude_code": "## Claude Code\n- 新增功能 [详情](https://example.com/claude)",
            "github_trending": "Repo A\nhttps://github.com/example/repo-a",
        },
        date="2026-05-18",
        generated_at="2026-05-18T07:15:00",
    )

    assert payload["date"] == "2026-05-18"
    assert payload["item_count"] == 2
    assert [item["topic"] for item in payload["items"]] == [
        "github_trending",
        "claude_code",
    ]
    assert payload["items"][1]["links"] == [
        {"title": "详情", "url": "https://example.com/claude"}
    ]
    assert payload["items"][0]["entries"] == [
        {"title": "Repo A", "url": "https://github.com/example/repo-a"}
    ]
    assert "每日 AI 监控汇总" in payload["full_text"]


def test_extract_links_deduplicates_markdown_and_plain_urls():
    links = extract_links(
        "[文档](https://example.com/doc)\n"
        "再看 https://example.com/doc\n"
        "还有 https://example.com/other."
    )

    assert links == [
        {"title": "文档", "url": "https://example.com/doc"},
        {"title": "https://example.com/other", "url": "https://example.com/other"},
    ]


def test_extract_entries_keeps_project_summary_and_visible_url():
    entries = extract_entries(
        "## GitHub Trending\n\n2026-07-10\n\n"
        "**owner/project**\n"
        "  A useful agent toolkit\n"
        "  🔗 https://github.com/owner/project\n"
        "\n---\n\n"
        "**owner/second**\n"
        "  Another project\n"
        "  🔗 https://github.com/owner/second\n"
    )

    assert entries == [
        {
            "title": "owner/project",
            "url": "https://github.com/owner/project",
            "summary": "A useful agent toolkit",
        },
        {
            "title": "owner/second",
            "url": "https://github.com/owner/second",
            "summary": "Another project",
        },
    ]


def test_build_payload_marks_no_update_sections():
    payload = build_payload(
        {"anthropic_engineering": "## Anthropic Engineering\n\n今日无新文章"},
        date="2026-07-10",
    )

    assert payload["items"][0]["status"] == "no_update"
