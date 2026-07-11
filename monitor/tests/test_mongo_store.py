from site_monitor.mongo_store import MongoMonitorStore


class FakeStateCollection:
    def __init__(self, documents=None):
        self.documents = {doc["filename"]: doc for doc in (documents or [])}

    def find(self, *args, **kwargs):
        return list(self.documents.values())

    def update_one(self, query, update, upsert=False):
        filename = query["filename"]
        current = self.documents.setdefault(filename, {"filename": filename})
        current.update(update.get("$setOnInsert", {}))
        current.update(update.get("$set", {}))


class RecordingCollection:
    def __init__(self):
        self.calls = []

    def update_one(self, query, update, upsert=False):
        self.calls.append((query, update, upsert))


def test_monitor_state_round_trip(tmp_path):
    collection = FakeStateCollection(
        [
            {"filename": "anthropic_state.json", "data": {"known_articles": ["a"]}},
            {"filename": "../unsafe.json", "data": {"ignored": True}},
        ]
    )
    store = object.__new__(MongoMonitorStore)
    store.monitor_state = collection

    restored = store.restore_monitor_state(tmp_path)
    assert restored == 1
    assert (tmp_path / "anthropic_state.json").read_text()
    assert not (tmp_path.parent / "unsafe.json").exists()

    (tmp_path / "github_state.json").write_text('{"repos": ["r1"]}')
    saved = store.save_monitor_state(tmp_path)

    assert saved == 2
    assert collection.documents["github_state.json"]["data"] == {"repos": ["r1"]}


def test_report_upsert_persists_ai_enrichment_fields():
    store = object.__new__(MongoMonitorStore)
    store.reports = RecordingCollection()
    store.items = RecordingCollection()
    payload = {
        "report_id": "2026-07-11-test",
        "date": "2026-07-11",
        "ai_enrichment": {
            "status": "success",
            "operations": ["title_translation", "article_summary"],
            "model": "test-model",
        },
        "items": [
            {
                "item_id": "2026-07-11-test:openai_news",
                "topic": "openai_news",
                "entries": [
                    {
                        "original_title": "Original",
                        "translated_title": "译文",
                        "summary_zh": "中文摘要",
                        "url": "https://example.com/article",
                    }
                ],
            }
        ],
    }

    store.upsert_report(payload)

    report_doc = store.reports.calls[0][1]["$set"]
    item_doc = store.items.calls[0][1]["$set"]
    assert report_doc["ai_enrichment"]["status"] == "success"
    assert report_doc["content_count"] == 1
    assert report_doc["content_item_count"] == 1
    assert item_doc["entry_count"] == 1
    assert item_doc["entries"][0]["translated_title"] == "译文"
    assert item_doc["entries"][0]["summary_zh"] == "中文摘要"
