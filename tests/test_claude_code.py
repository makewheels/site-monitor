from site_monitor import check_claude_code


def test_feature_release_is_important():
    release = {
        "tag": "v2.1.144",
        "body": "- Added new claude agents flags for model and permission-mode",
    }

    assert check_claude_code.is_important_release(release, old_tag="v2.1.143")


def test_plain_bugfix_release_is_not_important():
    release = {
        "tag": "v2.1.144",
        "body": "- Fixed crash when loading settings\n- Docs update",
    }

    assert not check_claude_code.is_important_release(release, old_tag="v2.1.143")


def test_security_fix_release_is_important():
    release = {
        "tag": "v2.1.144",
        "body": "- Fixed security issue in permission handling",
    }

    assert check_claude_code.is_important_release(release, old_tag="v2.1.143")


def test_minor_version_change_is_important_even_with_small_body():
    release = {
        "tag": "v2.2.0",
        "body": "- Fixed typo",
    }

    assert check_claude_code.is_important_release(release, old_tag="v2.1.143")
