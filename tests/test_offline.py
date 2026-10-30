"""Offline tests: compiler, validator and the repair/grounding step (no model needed).
Run: python -m unittest discover tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from medium import repair_and_ground  # noqa: E402
from n8n_compiler import compile_workflow  # noqa: E402
from validate import validate_workflow  # noqa: E402

SCRIPT = "# 0 3 * * * /bin/backup.sh\ntar czf /b.tgz /data\necho done | mail -s ok boss@example.com\n"


class Tests(unittest.TestCase):
    def plan(self):
        return {
            "workflow_name": "Backup",
            "trigger": {"type": "schedule", "cron": "0 3 * * * /bin/backup.sh"},
            "steps": [
                {"kind": "command", "name": "Archive", "detail": "tar czf /b.tgz /data"},
                {"kind": "http", "name": "Ping", "detail": "POST https://invented.example.net/x"},
                {"kind": "email", "name": "Tell boss", "detail": "mail boss@example.com"},
            ],
        }

    def test_repair_trims_cron_and_drops_hallucinated_url(self):
        p = self.plan()
        notes = repair_and_ground(p, SCRIPT)
        self.assertEqual(p["trigger"]["cron"], "0 3 * * *")
        self.assertEqual([s["name"] for s in p["steps"]], ["Archive", "Tell boss"])
        self.assertEqual(len(notes), 2)

    def test_compiled_workflow_is_valid(self):
        p = self.plan()
        repair_and_ground(p, SCRIPT)
        wf = compile_workflow(p, "backup.sh")
        self.assertEqual(validate_workflow(wf), [])
        self.assertEqual(wf["nodes"][0]["type"], "n8n-nodes-base.scheduleTrigger")

    def test_validator_catches_bad_cron_and_dangling_connection(self):
        wf = compile_workflow(self.plan(), "backup.sh")  # not repaired
        wf["connections"]["Archive"]["main"][0][0]["node"] = "Ghost node"
        errs = " ".join(validate_workflow(wf))
        self.assertIn("invalid cron", errs)
        self.assertIn("unknown node", errs)


if __name__ == "__main__":
    unittest.main()
