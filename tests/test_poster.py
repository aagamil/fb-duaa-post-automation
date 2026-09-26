import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import auto_poster as p


class PosterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root_patch = patch.object(p, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        (self.root / "images").mkdir()
        (self.root / "images/image_1.jpg").write_bytes(b"\xff\xd8\xfftest")
        p.save({"current_index": 1, "total_images": 1, "pending": None})
        env = patch.dict(p.os.environ, {"FB_PAGE_ACCESS_TOKEN": "test", "FB_GRAPH_API_VERSION": "v25.0", "FB_PAGE_ID": p.PAGE_ID})
        env.start()
        self.addCleanup(env.stop)

    def state(self):
        return json.loads((self.root / "state.json").read_text())

    def test_dry_run_no_side_effects(self):
        before = self.state()
        with patch.object(p, "api") as api:
            p.run(dry_run=True)
        api.assert_not_called()
        self.assertEqual(before, self.state())

    def test_success_and_wrap(self):
        with patch.object(p, "api", return_value={"id": p.PAGE_ID}), patch.object(p, "publish", return_value="photo123"), patch.object(p, "git_save") as commit:
            p.run(persist=True)
        self.assertEqual(commit.call_count, 2)
        self.assertEqual(self.state()["current_index"], 1)
        self.assertIsNone(self.state()["pending"])
        self.assertEqual(self.state()["last_post"]["photo_id"], "photo123")

    def test_failure_blocks_retry(self):
        with patch.object(p, "api", return_value={"id": p.PAGE_ID}), patch.object(p, "publish", side_effect=RuntimeError("timeout")):
            with self.assertRaises(RuntimeError):
                p.run()
        self.assertEqual(self.state()["current_index"], 1)
        with self.assertRaises(ValueError):
            p.load()

    def test_pending_commit_failure_prevents_publish(self):
        with patch.object(p, "api", return_value={"id": p.PAGE_ID}), patch.object(p, "git_save", side_effect=RuntimeError("push failed")), patch.object(p, "publish") as publish:
            with self.assertRaises(RuntimeError):
                p.run(persist=True)
        publish.assert_not_called()

    def test_missing_image(self):
        (self.root / "images/image_1.jpg").unlink()
        with self.assertRaises(ValueError):
            p.run(dry_run=True)

    def test_invalid_state(self):
        p.save({"current_index": 0, "total_images": 200})
        with self.assertRaises(ValueError):
            p.load()

    def test_advances(self):
        p.save({"current_index": 1, "total_images": 200})
        with patch.object(p, "api", return_value={"id": p.PAGE_ID}), patch.object(p, "publish", return_value="photo123"):
            p.run()
        self.assertEqual(self.state()["current_index"], 2)


if __name__ == "__main__":
    unittest.main()
