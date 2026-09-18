import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from vorhersage import research
from vorhersage.cli import main
from vorhersage.common import Error
from vorhersage.store import Store
from vorhersage.workflow import Workflow


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        Store(self.project).init("research")
        self.env = patch.dict("os.environ", {"EXA_API_KEY": "test-exa-secret", "FIRECRAWL_API_KEY": "test-firecrawl-secret"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def response(self, value):
        return io.BytesIO(json.dumps(value).encode())

    def cli(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            main(["--project", str(self.project), *args])
        return json.loads(output.getvalue())["data"]

    @patch("vorhersage.research.urlopen")
    def test_exa_search_persisted_and_offline_reuse(self, network):
        network.return_value = self.response({"results": [{"url": "https://example.com", "title": "Report"}],
                                             "requestId": "request-1", "costDollars": {"total": 0.005}})
        saved = self.cli("research", "search", "launch date", "--limit", "3")
        request = network.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.exa.ai/search")
        self.assertEqual(request.get_header("X-api-key"), "test-exa-secret")
        self.assertEqual(json.loads(request.data), {"query": "launch date", "numResults": 3, "type": "auto"})
        self.assertEqual(saved["sources"][0]["capture"]["method"], "discovery")
        self.assertNotIn("content", saved["sources"][0]["capture"])
        self.assertEqual(saved["usage"]["searches"], 1)
        self.assertEqual(saved["usage"]["provider_reported_cost"], {"total": 0.005})
        self.assertEqual(self.cli("research", "show", saved["id"]), saved)
        self.assertEqual(self.cli("research", "list")[0]["id"], saved["id"])
        network.assert_called_once()
        self.assertNotIn("test-exa-secret", json.dumps(saved))
        self.assertTrue(Workflow(self.project).doctor()["ok"])

    @patch("vorhersage.research.urlopen")
    def test_firecrawl_to_evidence_packet(self, network):
        network.return_value = self.response({"success": True, "data": {"markdown": "# Report\nService begins on Monday.",
            "metadata": {"title": "Launch", "sourceURL": "https://example.com/launch", "statusCode": 200}}})
        saved = self.cli("research", "fetch", "https://example.com/launch")
        request = network.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.firecrawl.dev/v2/scrape")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-firecrawl-secret")
        source = saved["sources"][0]
        self.assertEqual(source["capture"]["method"], "fetched")
        spec = {"findings": [{"id": "launch", "claim": "Service is scheduled for Monday.", "claim_type": "reporting",
                            "source_ids": [source["id"]], "claim_support": [{"source_id": source["id"],
                            "passage": "Service begins on Monday.", "relation": "direct", "rationale": "The announcement supplies a date."}]}],
                "limitations": ["Schedule may change."]}
        path = self.project / "findings.json"
        path.write_text(json.dumps(spec))
        result = self.cli("research", "capture", "--retrieval", saved["id"], "--from", str(path))
        self.assertIn("packet_id", result)
        with Store(self.project).connect() as c:
            packet = Store.artifact(c, result["packet_id"], "packet")
        self.assertEqual(packet["records"][0]["sources"][0], source)
        self.assertTrue(Workflow(self.project).doctor()["ok"])
        spec["findings"][0]["claim_support"][0]["passage"] = "Fabricated passage"
        with self.assertRaisesRegex(Error, "passage must occur"):
            research.capture(self.project, [saved["id"]], spec)
        spec["sources"] = [source]
        with self.assertRaisesRegex(Error, "sources come from"):
            research.capture(self.project, [saved["id"]], spec)

    @patch("vorhersage.research.urlopen")
    def test_other_provider_operations(self, network):
        network.return_value = self.response({"success": True, "data": {"web": [{"url": "https://example.com", "markdown": "Page text"}]}})
        saved = research.search(self.project, "report", provider="firecrawl", include_content=True)
        self.assertEqual(json.loads(network.call_args.args[0].data)["scrapeOptions"], {"formats": ["markdown"]})
        self.assertEqual(saved["sources"][0]["capture"]["content"], "Page text")
        network.return_value = self.response({"results": [{"url": "https://example.com", "text": "Page text"}],
            "statuses": [{"id": "https://example.com", "status": "success", "source": "cached"}]})
        saved = research.fetch(self.project, "https://example.com", provider="exa")
        self.assertEqual(network.call_args.args[0].full_url, "https://api.exa.ai/contents")
        self.assertEqual(json.loads(network.call_args.args[0].data), {"ids": ["https://example.com"], "text": True})
        self.assertEqual(saved["usage"]["searches"], 0)
        self.assertEqual(saved["sources"][0]["capture"]["content"], "Page text")
        network.return_value = self.response({"results": []})
        research.search(self.project, "report", include_content=True)
        self.assertEqual(json.loads(network.call_args.args[0].data)["contents"], {"text": True})

    @patch("vorhersage.research.urlopen")
    def test_empty_and_unsuccessful_results_are_retained(self, network):
        network.return_value = self.response({"results": []})
        self.assertEqual(research.search(self.project, "obscure")["sources"], [])
        network.return_value = self.response({"results": [], "statuses": [{"id": "https://example.com", "status": "error"}]})
        saved = research.fetch(self.project, "https://example.com", provider="exa")
        self.assertTrue(saved["warnings"])
        self.assertEqual(saved["sources"], [])
        network.return_value = self.response({"success": True, "data": {"markdown": "Not found", "metadata": {"statusCode": 404}}})
        saved = research.fetch(self.project, "https://example.com")
        self.assertTrue(saved["warnings"])
        self.assertEqual(saved["sources"], [])
        network.return_value = self.response({"success": True, "data": {"metadata": {"title": "Empty page"}}})
        saved = research.fetch(self.project, "https://example.com")
        self.assertEqual(saved["sources"][0]["capture"]["method"], "discovery")
        self.assertTrue(saved["warnings"])

    @patch("vorhersage.research.urlopen")
    def test_validation_precedes_network(self, network):
        for kwargs in ({"limit": 0}, {"limit": True}, {"provider": "other"}, {"timeout": float("nan")}, {"question": "unknown"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(Error):
                research.search(self.project, "test", **kwargs)
        for url in ("file:///etc/passwd", "https://user:secret@example.com", ""):
            with self.assertRaises(Error):
                research.fetch(self.project, url)
        with self.assertRaises(Error):
            research.search(self.project / "uninitialized", "test")
        with patch.dict("os.environ", {"EXA_API_KEY": ""}), self.assertRaisesRegex(Error, "EXA_API_KEY"):
            research.search(self.project, "test")
        network.assert_not_called()

    @patch("vorhersage.research.urlopen")
    def test_errors_are_sanitized_and_never_retried(self, network):
        errors = [HTTPError("https://api.exa.ai/search", 429, "test-exa-secret", {}, io.BytesIO(b"test-exa-secret")),
                  URLError("test-exa-secret"), TimeoutError("test-exa-secret")]
        for exc in errors:
            network.reset_mock()
            network.side_effect = exc
            with self.assertRaises(Error) as caught:
                research.search(self.project, "test")
            self.assertNotIn("test-exa-secret", str(caught.exception))
            network.assert_called_once()
        self.assertEqual(research.list_retrievals(self.project), [])

    @patch("vorhersage.research.urlopen")
    def test_malformed_and_oversized_responses(self, network):
        for response in (b"not json", b"[]", b'{"results":null}', b'{"error":"test-exa-secret"}', b'{"results":[],"cost":NaN}'):
            network.return_value = io.BytesIO(response)
            with self.assertRaises(Error) as caught:
                research.search(self.project, "test")
            self.assertNotIn("test-exa-secret", str(caught.exception))
        network.return_value = io.BytesIO(b"x" * 101)
        with patch.object(research, "MAX_RESPONSE_BYTES", 100), self.assertRaisesRegex(Error, "size limit"):
            research.search(self.project, "test")
        self.assertEqual(research.list_retrievals(self.project), [])


if __name__ == "__main__":
    unittest.main()
