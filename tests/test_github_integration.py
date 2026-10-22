import unittest
from unittest.mock import patch

from core import github_integration as gh


class GitHubIntegrationTests(unittest.TestCase):
    def test_repo_path_rejects_injection(self):
        with self.assertRaises(gh.GitHubError):
            gh._repo("../owner", "repo")
        with self.assertRaises(gh.GitHubError):
            gh._repo("owner", "repo?per_page=999")

    def test_branch_name_rejects_default_branch(self):
        with self.assertRaises(gh.GitHubError):
            gh.create_branch("owner", "repo", "main", "main")

    def test_branch_name_rejects_path_traversal(self):
        with self.assertRaises(gh.GitHubError):
            gh.create_branch("owner", "repo", "../oops", "main")

    @patch.object(gh, "request")
    def test_create_issue_validates_title_before_network(self, request):
        with self.assertRaises(gh.GitHubError):
            gh.create_issue("owner", "repo", " " * 3)
        request.assert_not_called()

    @patch.object(gh, "request")
    def test_create_pull_request_rejects_same_head_and_base(self, request):
        with self.assertRaises(gh.GitHubError):
            gh.create_pull_request("owner", "repo", "Example", "feature/x", "feature/x")
        request.assert_not_called()

    @patch.object(gh, "request")
    def test_create_issue_sends_expected_payload(self, request):
        request.return_value = {"number": 9, "html_url": "https://github.com/o/r/issues/9", "title": "Fix"}
        result = gh.create_issue("o", "r", " Fix ", "Details")
        self.assertEqual(result["number"], 9)
        request.assert_called_once_with("POST", "/repos/o/r/issues", {"title": "Fix", "body": "Details"})

    @patch.object(gh, "request")
    def test_branch_creation_uses_selected_source_sha(self, request):
        request.side_effect = [
            {"object": {"sha": "abc123"}},
            {"object": {"sha": "def456"}},
        ]
        result = gh.create_branch("owner", "repo", "feature/work", "main")
        self.assertEqual(result["sha"], "def456")
        self.assertEqual(request.call_count, 2)
        self.assertEqual(request.call_args_list[1].args[1], "/repos/owner/repo/git/refs")


if __name__ == "__main__":
    unittest.main()
