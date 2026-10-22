import unittest
from unittest.mock import call, patch

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

    def test_branch_creation_rejects_invalid_source_before_network(self):
        with patch.object(gh, "request") as request:
            with self.assertRaises(gh.GitHubError):
                gh.create_branch("owner", "repo", "feature/work", "../../user")
            request.assert_not_called()

    def test_branch_creation_rejects_invalid_ref_components_before_network(self):
        with patch.object(gh, "request") as request:
            with self.assertRaises(gh.GitHubError):
                gh.create_branch("owner", "repo", "feature//work", "main")
            request.assert_not_called()

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
        request.return_value = {
            "number": 9,
            "html_url": "https://github.com/o/r/issues/9",
            "title": "Fix",
        }
        result = gh.create_issue("o", "r", " Fix ", "Details")
        self.assertEqual(result["number"], 9)
        request.assert_called_once_with(
            "POST", "/repos/o/r/issues", {"title": "Fix", "body": "Details"}
        )

    @patch.object(gh, "request")
    def test_branch_creation_uses_selected_source_sha(self, request):
        request.side_effect = [
            {"object": {"sha": "abc123"}},
            {"object": {"sha": "def456"}},
        ]
        result = gh.create_branch("owner", "repo", "feature/work", "main")
        self.assertEqual(result["sha"], "def456")
        self.assertEqual(request.call_count, 2)
        self.assertEqual(
            request.call_args_list[1].args[1], "/repos/owner/repo/git/refs"
        )

    @patch.object(gh, "request")
    def test_overview_includes_repositories_after_first_page(self, request):
        first_page = [
            {
                "full_name": f"owner/repo-{i}",
                "private": False,
                "default_branch": "main",
            }
            for i in range(gh.PAGE_SIZE)
        ]
        second_page = [
            {
                "full_name": "oORaxaOo/Kor-Eternal_Frontier",
                "private": False,
                "default_branch": "main",
            },
            {
                "full_name": "oORaxaOo/Kor-Motorforge",
                "private": False,
                "default_branch": "main",
            },
        ]
        request.side_effect = [
            {"login": "oORaxaOo", "avatar_url": ""},
            first_page,
            second_page,
        ]

        result = gh.overview()

        names = [repo["full_name"] for repo in result["repositories"]]
        self.assertEqual(len(names), gh.PAGE_SIZE + 2)
        self.assertIn("oORaxaOo/Kor-Eternal_Frontier", names)
        self.assertIn("oORaxaOo/Kor-Motorforge", names)
        self.assertEqual(request.call_count, 3)
        self.assertIn("page=1", request.call_args_list[1].args[1])
        self.assertIn("page=2", request.call_args_list[2].args[1])

    def test_pagination_fails_instead_of_silently_truncating(self):
        with patch.object(gh, "request", side_effect=[
            [{"name": "one"}],
            [{"name": "two"}],
            [{"name": "three"}],
        ]) as request:
            with self.assertRaisesRegex(gh.GitHubError, "nicht stillschweigend gekürzt"):
                gh._list_all_pages("/repos/example/branches", page_size=1, max_pages=2)
        self.assertEqual(request.call_count, 3)

    def test_pagination_rejects_unexpected_response_type(self):
        with patch.object(gh, "request", return_value={"message": "not a list"}):
            with self.assertRaisesRegex(gh.GitHubError, "Listen-Antwort"):
                gh._list_all_pages("/user/repos")


if __name__ == "__main__":
    unittest.main()
