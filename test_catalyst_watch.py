"""Tests for the fail-closed Catalyst Watch evidence contract."""

import io
import json
import tempfile
import unittest
from pathlib import Path

from catalyst_watch import build_catalyst_watch


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class CatalystWatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "watch.json"

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, cases):
        self.path.write_text(json.dumps({"updatedAt": "2026-08-05T00:00:00Z", "cases": cases}))

    def _case(self):
        return {
            "symbol": "TEST", "cik": "123", "currentStage": "possible",
            "monitorSince": "2026-01-01T00:00:00Z",
            "timeline": [
                {"stage": "possible", "publishedAt": "2026-01-01T10:00:00Z",
                 "headline": "Possible", "evidenceStatus": "verified",
                 "source": {"name": "Issuer", "url": "https://example.com/one"}},
                {"stage": "developing", "publishedAt": "2026-02-01T10:00:00Z",
                 "headline": "Developing", "evidenceStatus": "provisional",
                 "source": {"name": "Report", "url": "https://example.com/two"}},
            ],
        }

    def test_keeps_verified_and_provisional_evidence_distinct(self):
        self._write([self._case()])
        payload = build_catalyst_watch(self.path, live=False)
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["cases"][0]["timeline"][1]["evidenceStatus"], "provisional")
        self.assertEqual(payload["cases"][0]["currentStage"], "possible")
        self.assertTrue(payload["researchOnly"])

    def test_rejects_stage_regression(self):
        case = self._case()
        case["timeline"].append({
            "stage": "possible", "publishedAt": "2026-03-01T10:00:00Z",
            "headline": "Regressed", "evidenceStatus": "verified",
            "source": {"name": "Issuer", "url": "https://example.com/three"},
        })
        self._write([case])
        payload = build_catalyst_watch(self.path, live=False)
        self.assertEqual(payload["status"], "empty")
        self.assertEqual(payload["invalidCases"], 1)

    def test_provisional_evidence_cannot_promote_the_official_stage(self):
        case = self._case()
        case["currentStage"] = "developing"
        self._write([case])
        payload = build_catalyst_watch(self.path, live=False)
        self.assertEqual(payload["status"], "empty")

    def test_surfaces_new_sec_filings_without_auto_escalation(self):
        self._write([self._case()])
        sec = {"filings": {"recent": {
            "form": ["8-K"], "accessionNumber": ["0000000123-26-000001"],
            "primaryDocument": ["test.htm"], "acceptanceDateTime": ["2026-03-01T12:30:00Z"],
        }}}

        def opener(_request, timeout=0):
            self.assertEqual(timeout, 8)
            return _Response(json.dumps(sec).encode())

        payload = build_catalyst_watch(self.path, live=True, opener=opener)
        filing = payload["cases"][0]["liveSec"]["newFilings"][0]
        self.assertEqual(filing["form"], "8-K")
        self.assertFalse(filing["autoEscalated"])


if __name__ == "__main__":
    unittest.main()
