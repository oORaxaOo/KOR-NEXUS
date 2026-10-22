"""Regression tests for the local code-workbench workspace boundary."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import server


class CodeWorkbenchWorkspaceTests(unittest.TestCase):
    def test_configured_roots_are_canonical_and_existing_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            first = base / "projects"
            second = base / "games"
            first.mkdir()
            second.mkdir()
            missing = base / "does-not-exist"
            configured = os.pathsep.join((str(first), str(first / "."), str(second), str(missing)))
            with patch.dict(os.environ, {"KOR_WORKSPACE_ROOTS": configured}):
                roots = server._ide_workspace_roots()
            self.assertEqual(roots, [first.resolve(), second.resolve()])

    def test_default_roots_are_filtered_to_existing_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            project_root = Path(temporary) / "workspace"
            project_root.mkdir()
            with patch.dict(os.environ, {"KOR_WORKSPACE_ROOTS": str(project_root)}):
                roots = server._ide_workspace_roots()
            self.assertEqual(roots, [project_root.resolve()])
            self.assertTrue(all(root.is_dir() for root in roots))

    def test_workspace_listing_only_includes_projects_or_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "KOR-Eternal-Frontier"
            repo.mkdir()
            (repo / ".git").mkdir()
            plain = root / "random-folder"
            plain.mkdir()
            project = root / "Kor-Motorforge"
            project.mkdir()
            (project / "pyproject.toml").write_text("[project]\nname='motorforge'\n", encoding="utf-8")
            with patch.dict(os.environ, {"KOR_WORKSPACE_ROOTS": str(root)}):
                roots = server._ide_workspace_roots()
            self.assertEqual(roots, [root.resolve()])
            candidates = [roots[0], *sorted((p for p in roots[0].iterdir() if p.is_dir() and not p.name.startswith(".")), key=lambda p: p.name.lower())]
            offered = []
            for candidate in candidates:
                resolved = candidate.resolve(strict=True)
                if candidate == roots[0] or (resolved / ".git").exists() or any((resolved / marker).exists() for marker in ("pyproject.toml", "package.json", "Cargo.toml", "CMakeLists.txt", ".sln")):
                    offered.append(resolved.name)
            self.assertIn("KOR-Eternal-Frontier", offered)
            self.assertIn("Kor-Motorforge", offered)
            self.assertNotIn("random-folder", offered)


if __name__ == "__main__":
    unittest.main()
