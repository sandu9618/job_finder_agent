"""Tests for JobSpy client response parsing (no live MCP/Docker)."""

import json
import unittest
from types import SimpleNamespace

from job_finder_agent.mcp_servers.jobspy_client import (
    _extract_jobs_payload,
    _parse_mcp_tool_result,
    _snake_to_camel,
    _to_mcp_arguments,
)


class TestJobSpyClientHelpers(unittest.TestCase):
    def test_snake_to_camel(self):
        self.assertEqual(_snake_to_camel("search_term"), "searchTerm")
        self.assertEqual(_snake_to_camel("site_names"), "siteNames")

    def test_to_mcp_arguments(self):
        args = _to_mcp_arguments(
            {"search_term": "engineer", "results_wanted": 5, "is_remote": True}
        )
        self.assertEqual(
            args,
            {"searchTerm": "engineer", "resultsWanted": 5, "isRemote": True},
        )

    def test_extract_jobs_payload_list(self):
        jobs = [{"title": "Dev"}]
        self.assertEqual(_extract_jobs_payload(jobs), jobs)

    def test_extract_jobs_payload_wrapped(self):
        payload = {"count": 1, "jobs": [{"title": "Dev"}]}
        self.assertEqual(_extract_jobs_payload(payload), [{"title": "Dev"}])

    def test_parse_mcp_tool_result(self):
        text = json.dumps({"count": 1, "jobs": [{"title": "Analyst", "jobUrl": "http://x"}]})
        result = SimpleNamespace(
            isError=False,
            content=[SimpleNamespace(text=text)],
        )
        jobs = _parse_mcp_tool_result(result)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["title"], "Analyst")

    def test_parse_mcp_tool_result_error(self):
        result = SimpleNamespace(isError=True, content=[])
        with self.assertRaises(RuntimeError):
            _parse_mcp_tool_result(result)


if __name__ == "__main__":
    unittest.main()
