"""Core logic tests (no GUI).  Run:  python -m unittest discover -s tests -v"""
import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from ideavault import exporter
from ideavault.database import IdeaRepository, normalize_tags


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.repo = IdeaRepository(self.dir / "ideas.db")

    def tearDown(self):
        self.repo.close()
        self.tmp.cleanup()

    def test_create_and_get(self):
        idea = self.repo.create("Code", title="Parser", content="Use a Pratt parser", tags="python, ,Python,#ast")
        self.assertEqual(idea.category, "Code")
        self.assertEqual(idea.tags, "python, ast")
        self.assertEqual(self.repo.get(idea.id).title, "Parser")

    def test_update_noop_keeps_timestamp(self):
        idea = self.repo.create(title="A")
        time.sleep(1.1)
        same = self.repo.update(idea.id, title="A")
        self.assertEqual(same.updated_at, idea.updated_at)
        changed = self.repo.update(idea.id, title="B")
        self.assertNotEqual(changed.updated_at, idea.updated_at)
        self.assertEqual(changed.created_at, idea.created_at)

    def test_search_and_filters(self):
        self.repo.create("Code", title="CLI tool", content="argparse wrapper", tags="python")
        self.repo.create("Writing", title="Blog post", content="On 100% focus", tags="essay")
        self.repo.create("Projects", title="Garden", content="raised beds", tags="outdoor, python")
        self.assertEqual(len(self.repo.list_ideas()), 3)
        self.assertEqual(len(self.repo.list_ideas("Code")), 1)
        self.assertEqual(len(self.repo.list_ideas(query="python")), 2)
        self.assertEqual(len(self.repo.list_ideas(query="#python garden")), 1)
        self.assertEqual(len(self.repo.list_ideas(query="100%")), 1)   # LIKE wildcards escaped
        self.assertEqual(len(self.repo.list_ideas(query="ARGPARSE")), 1)  # case-insensitive
        counts = self.repo.category_counts()
        self.assertEqual(counts["__total__"], 3)
        self.assertEqual(counts["Writing"], 1)

    def test_delete(self):
        idea = self.repo.create()
        self.repo.delete(idea.id)
        self.assertIsNone(self.repo.get(idea.id))

    def test_backup(self):
        self.repo.create(title="Keep me")
        dest = self.repo.backup_to(self.dir / "backup.db")
        rows = sqlite3.connect(dest).execute("SELECT title FROM ideas").fetchall()
        self.assertEqual(rows, [("Keep me",)])

    def test_export_import_roundtrip(self):
        self.repo.create("Code", title="One", content="# Heading\n- item", tags="a, b")
        self.repo.create("To-Do", title="Two")
        out = self.dir / "out"
        out.mkdir()
        jpath = exporter.export_json(self.repo.all_ideas(), out)
        mpath = exporter.export_markdown(self.repo.all_ideas(), out)
        payload = json.loads(jpath.read_text(encoding="utf-8"))
        self.assertEqual(payload["count"], 2)
        self.assertIn("### One", mpath.read_text(encoding="utf-8"))

        # Re-importing into the same vault skips duplicates
        self.assertEqual(exporter.import_json(self.repo, jpath), (0, 2))
        other = IdeaRepository(self.dir / "other.db")
        try:
            self.assertEqual(exporter.import_json(other, jpath), (2, 0))
            self.assertEqual({i.title for i in other.all_ideas()}, {"One", "Two"})
        finally:
            other.close()

    def test_normalize_tags(self):
        self.assertEqual(normalize_tags(" ui,UI , #ux,, "), "ui, ux")


if __name__ == "__main__":
    unittest.main()
