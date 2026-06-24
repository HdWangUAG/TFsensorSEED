"""Focused, pure-stdlib regression tests for MiniCrew core pieces.

No pytest required — run with the project venv (or any python3 with pyyaml):

    minicrew/.venv/bin/python -m unittest discover -s minicrew/tests
    # or directly:
    minicrew/.venv/bin/python minicrew/tests/test_core.py

Each test redirects the on-disk locations (knowledge / runs / conversations) to a
TemporaryDirectory so it never touches the real worktree.
"""
import os
import sys
import tempfile
import unittest

# make `minicrew.core...` importable when run as a plain script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from minicrew.core import config, logger, memory  # noqa: E402


class _TmpDirs(unittest.TestCase):
    """Point config at a throwaway tree; restore originals on teardown."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = self._tmp.name
        self._saved = {k: getattr(config, k)
                       for k in ("KNOWLEDGE_DIR", "RUNS_DIR", "CONV_DIR")}
        config.KNOWLEDGE_DIR = os.path.join(root, "knowledge")
        config.RUNS_DIR = os.path.join(root, "runs")
        config.CONV_DIR = os.path.join(root, "conversations")

    def tearDown(self):
        for k, v in self._saved.items():
            setattr(config, k, v)
        self._tmp.cleanup()


class SupersedeNoteTest(_TmpDirs):
    def test_note_is_persisted(self):
        rec = memory.make_record("decision", "Use Boltz for the holo fold.")
        memory.write_record(rec)
        new = memory.make_record("decision", "Switch to wet-lab validation.")
        memory.write_record(new)

        path = memory.supersede(rec["id"], new_id=new["id"],
                                note="reversed after the BO surrogate disagreed")

        reloaded = memory.parse(path)
        self.assertEqual(reloaded["status"], "superseded")
        self.assertEqual(reloaded["superseded_by"], new["id"])
        # the note must survive in BOTH frontmatter and the rendered body
        self.assertEqual(reloaded["supersession_note"],
                         "reversed after the BO surrogate disagreed")
        self.assertIn("reversed after the BO surrogate disagreed",
                      reloaded["_body"])

    def test_missing_record_raises(self):
        with self.assertRaises(KeyError):
            memory.supersede("dec_doesnotexist")


class PromoteTest(_TmpDirs):
    def test_candidate_is_hidden_then_promoted(self):
        from minicrew.core import kdb
        rec = memory.make_record("pitfall", "Do not trust a single coarse fold.",
                                 status="candidate", severity="medium")
        memory.write_record(rec)
        # candidate is hidden from default recall...
        self.assertEqual(kdb.search("", types=["pitfall"]), [])
        # ...but visible when explicitly asked for
        self.assertEqual(len(kdb.search("", types=["pitfall"], status="candidate")), 1)

        path = memory.promote(rec["id"], note="confirmed in the L147R campaign")
        back = memory.parse(path)
        self.assertEqual(back["status"], "active")
        self.assertEqual(back["promotion_note"], "confirmed in the L147R campaign")
        self.assertIn("confirmed in the L147R campaign", back["_body"])
        # now it IS recalled by default
        self.assertEqual(len(kdb.search("", types=["pitfall"])), 1)

    def test_promote_rejects_inactive_target(self):
        rec = memory.make_record("pitfall", "x", status="candidate")
        memory.write_record(rec)
        with self.assertRaises(ValueError):
            memory.promote(rec["id"], to="superseded")

    def test_promote_missing_raises(self):
        with self.assertRaises(KeyError):
            memory.promote("pit_doesnotexist")


class MemoryRoundtripTest(_TmpDirs):
    def test_record_roundtrips(self):
        rec = memory.make_record(
            "claim", "Testosterone binds the AcrR pocket with high selectivity.",
            confidence="high", status="supported")
        path = memory.write_record(rec)
        back = memory.parse(path)
        self.assertEqual(back["type"], "claim")
        self.assertEqual(back["status"], "supported")
        self.assertEqual(back["confidence"], "high")
        self.assertEqual(back["text"], rec["text"])
        # auto-tags fired on vocab terms
        self.assertIn("testosterone", back["tags"])
        self.assertIn("selectivity", back["tags"])


class LoggerPathsTest(_TmpDirs):
    def _crew(self):
        return {"name": "demo", "task": "review the plan"}

    def _transcript(self):
        return [{"role": "Reviewer", "alias": "claude", "model": "x",
                 "kind": "reviewer", "ok": True,
                 "prompt_seen": "the prompt", "content": "the reply"}]

    def test_default_paths(self):
        rec = logger.save_run(self._crew(), "round_robin", self._transcript())
        # md and json both reported, both exist, both under the configured dirs
        self.assertTrue(os.path.isfile(rec["md_path"]))
        self.assertTrue(os.path.isfile(rec["json_path"]))
        self.assertEqual(os.path.dirname(rec["md_path"]), config.CONV_DIR)
        self.assertEqual(os.path.dirname(rec["json_path"]), config.RUNS_DIR)

    def test_out_path_redirects_md_only(self):
        out = os.path.join(self._tmp.name, "elsewhere", "review.md")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        rec = logger.save_run(self._crew(), "round_robin",
                              self._transcript(), out_path=out)
        # --out moves the markdown but NOT the json record
        self.assertEqual(rec["md_path"], out)
        self.assertTrue(os.path.isfile(out))
        self.assertEqual(os.path.dirname(rec["json_path"]), config.RUNS_DIR)
        self.assertTrue(os.path.isfile(rec["json_path"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
