# Git and Git LFS operations — no bpy dependency.
from __future__ import annotations

import os
import re
import subprocess


def _build_env() -> dict[str, str]:
    """Return an env dict whose PATH includes common macOS/Linux install dirs.

    Blender on macOS launches with a minimal PATH that often excludes
    /opt/homebrew/bin, /usr/local/bin, etc., causing git-lfs (and sometimes
    git itself) to appear missing even when installed.
    """
    env = os.environ.copy()
    extra = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]
    existing = env.get("PATH", "")
    for p in extra:
        if p not in existing:
            existing = p + os.pathsep + existing
    env["PATH"] = existing
    return env


_ENV = _build_env()


class GitOps:

    # ------------------------------------------------------------------ #
    #  Private helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _run_git(args: list[str], cwd: str) -> subprocess.CompletedProcess:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            env=_ENV,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
        return result

    @staticmethod
    def _write_gitattributes(repo_path: str) -> None:
        path = os.path.join(repo_path, ".gitattributes")
        with open(path, "w", encoding="utf-8") as f:
            f.write("*.blend filter=lfs diff=lfs merge=lfs -text\n")

    @staticmethod
    def _write_gitignore(repo_path: str) -> None:
        path = os.path.join(repo_path, ".gitignore")
        with open(path, "w", encoding="utf-8") as f:
            f.write("*.blend1\n__pycache__/\n*.pyc\n.DS_Store\n")

    @staticmethod
    def _parse_refs(refs_raw: str) -> list[str]:
        if not refs_raw:
            return []
        return [ref.strip() for ref in refs_raw.split(", ") if ref.strip()]

    def _extract_local_branch_refs(self, refs: list[str], repo_path: str) -> list[str]:
        try:
            local_branches = {
                branch["name"] for branch in self.list_branches(repo_path)
            }
        except RuntimeError:
            local_branches = set()

        branch_refs: list[str] = []
        for ref in refs:
            if ref.startswith("HEAD -> "):
                candidate = ref.split("HEAD -> ", 1)[1].strip()
            else:
                candidate = ref.strip()
            if candidate in local_branches and candidate not in branch_refs:
                branch_refs.append(candidate)
        return branch_refs

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    @staticmethod
    def check_dependencies() -> dict[str, bool]:
        try:
            git_ok = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                check=False,
                env=_ENV,
            ).returncode == 0
        except FileNotFoundError:
            git_ok = False

        try:
            lfs_ok = subprocess.run(
                ["git", "lfs", "version"],
                capture_output=True,
                check=False,
                env=_ENV,
            ).returncode == 0
        except FileNotFoundError:
            lfs_ok = False

        return {"git": git_ok, "git_lfs": lfs_ok}

    @staticmethod
    def is_git_repo(path: str) -> bool:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=path,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0

    def init_repo(self, repo_path: str) -> None:
        self._run_git(["init", "--initial-branch=main"], cwd=repo_path)
        self._run_git(["lfs", "install"], cwd=repo_path)
        self._write_gitattributes(repo_path)
        self._write_gitignore(repo_path)
        self._run_git(["add", "-A"], cwd=repo_path)
        self._run_git(["commit", "-m", "Initialize project"], cwd=repo_path)

    def has_uncommitted_changes(self, repo_path: str) -> bool:
        result = self._run_git(["status", "--porcelain"], cwd=repo_path)
        return bool(result.stdout.strip())

    def commit(self, repo_path: str, message: str) -> str:
        if not self.has_uncommitted_changes(repo_path):
            raise RuntimeError("There are no changes to save.")
        self._run_git(["add", "-A"], cwd=repo_path)
        self._run_git(["commit", "-m", message], cwd=repo_path)
        result = self._run_git(["rev-parse", "--short", "HEAD"], cwd=repo_path)
        return result.stdout.strip()

    def get_current_branch(self, repo_path: str) -> str | None:
        result = self._run_git(["branch", "--show-current"], cwd=repo_path)
        name = result.stdout.strip()
        return name if name else None

    def list_branches(self, repo_path: str) -> list[dict]:
        result = self._run_git(
            ["branch", "--format=%(refname:short)|%(HEAD)"], cwd=repo_path
        )
        branches: list[dict] = []
        for line in result.stdout.strip().splitlines():
            if not line:
                continue
            parts = line.split("|")
            name = parts[0].strip()
            is_current = len(parts) > 1 and parts[1].strip() == "*"
            branches.append({"name": name, "is_current": is_current})
        return branches

    def create_branch(self, repo_path: str, name: str) -> None:
        self._run_git(["checkout", "-b", name], cwd=repo_path)

    def checkout(self, repo_path: str, ref: str) -> None:
        if self.has_uncommitted_changes(repo_path):
            raise RuntimeError(
                "Please save your work before switching branches."
            )
        self._run_git(["checkout", ref], cwd=repo_path)

    def get_branch_lineages(
        self,
        repo_path: str,
        max_count: int = 150,
    ) -> dict[str, list[str]]:
        lineages: dict[str, list[str]] = {}
        try:
            branches = self.list_branches(repo_path)
        except RuntimeError:
            return lineages

        for branch in branches:
            name = branch["name"]
            try:
                result = self._run_git(
                    [
                        "rev-list",
                        "--first-parent",
                        name,
                        f"--max-count={max_count}",
                    ],
                    cwd=repo_path,
                )
            except RuntimeError:
                continue
            hashes = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            lineages[name] = hashes
        return lineages

    def get_timeline(self, repo_path: str, max_count: int = 150) -> list[dict]:
        try:
            result = self._run_git(
                [
                    "log",
                    "--all",
                    "--topo-order",
                    "--decorate=short",
                    "--format=%H%x00%h%x00%s%x00%D%x00%ct%x00%P",
                    f"--max-count={max_count}",
                ],
                cwd=repo_path,
            )
        except RuntimeError:
            return []

        entries: list[dict] = []
        for line in result.stdout.strip().splitlines():
            if not line:
                continue
            parts = line.split("\x00")
            if len(parts) < 6:
                continue
            refs = self._parse_refs(parts[3].strip())
            entries.append({
                "hash": parts[0],
                "short_hash": parts[1],
                "message": parts[2],
                "refs": refs,
                "branch_refs": self._extract_local_branch_refs(refs, repo_path),
                "timestamp": int(parts[4]),
                "parents": [parent for parent in parts[5].split() if parent],
            })
        return entries

    def get_log(self, repo_path: str, max_count: int = 100) -> list[dict]:
        entries = self.get_timeline(repo_path, max_count=max_count)
        return [
            {
                "hash": entry["hash"],
                "short_hash": entry["short_hash"],
                "message": entry["message"],
                "refs": entry["refs"],
                "timestamp": entry["timestamp"],
            }
            for entry in entries
        ]

    @staticmethod
    def sanitize_branch_name(name: str) -> str:
        name = name.strip()
        # Replace spaces and backslashes with dashes
        name = re.sub(r"[\s\\]+", "-", name)
        # Remove forbidden characters
        name = re.sub(r"[~^:?*\[\]]+", "", name)
        # Collapse consecutive dots
        name = re.sub(r"\.{2,}", ".", name)
        # Strip leading . - _
        name = name.lstrip(".-_")
        # Strip trailing .lock
        name = re.sub(r"\.lock$", "", name)
        # Strip trailing . and -
        name = name.rstrip(".-")
        # Collapse consecutive dashes
        name = re.sub(r"-{2,}", "-", name)

        if not name:
            raise RuntimeError("Please enter a valid branch name.")
        return name


git_ops = GitOps()
