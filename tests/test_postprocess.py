from site_monitor.postprocessors.changelog import split_changelog_sections


def test_changelog_postprocessor_splits_features_and_fixes():
    payload = {
        "body": "- Added plugin support\n- Fixed crash on startup\n- Docs update",
    }

    result = split_changelog_sections(payload, {"include_fixes": True})

    assert "### 功能更新" in result["summary"]
    assert "- Added plugin support" in result["summary"]
    assert "---\n### 修复/其他" in result["summary"]
    assert "- Fixed crash on startup" in result["summary"]
    assert result["feature_count"] == 1
    assert result["fix_count"] == 2
    assert result["should_notify"] is True


def test_changelog_postprocessor_can_suppress_fix_only_updates():
    payload = {
        "body": "- Fixed typo\n- Docs update",
    }

    result = split_changelog_sections(
        payload,
        {"include_fixes": True, "notify_only_feature_updates": True},
    )

    assert "暂无明显功能更新" in result["summary"]
    assert result["feature_count"] == 0
    assert result["fix_count"] == 2
    assert result["should_notify"] is False
