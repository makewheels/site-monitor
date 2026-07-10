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
