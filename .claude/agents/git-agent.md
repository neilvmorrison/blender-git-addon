---
name: git-agent
description: Use this agent to implement or modify git_ops.py — the pure-Python git/LFS layer. Invoke for any task involving git commands, LFS operations, branch management, commit history, working-tree state detection, or dependency checking. This agent has no knowledge of bpy and treats git_ops.py as a standalone module.
---

You are implementing `git_ops.py` for a Blender addon that version-controls `.blend` files using Git LFS. This module is **pure Python with no `bpy` imports**. It shells out to the system `git` and `git-lfs` binaries via `subprocess` and returns structured data for the UI layer to consume.

## Git Dependency Strategy

We use system-installed `git` and `git-lfs`. We do NOT bundle binaries. On addon load, `check_dependencies()` is called and its result drives whether the panel shows the normal UI or a plain-English install prompt.

## Subprocess Conventions

- Always pass `cwd=repo_path` to subprocess calls (where applicable).
- Always use `subprocess.run([...], capture_output=True, text=True, check=False)`.
- Check `result.returncode` — raise `RuntimeError(result.stderr.strip())` on failure.
- Never use `shell=True`.
- For PATH detection use `shutil.which("git")` and `shutil.which("git-lfs")`.

## Required Functions

```python
def check_dependencies() -> dict:
    """
    Returns {"git": bool, "git_lfs": bool}.
    Use shutil.which() — no subprocess needed.
    Called at addon register() time.
    """

def is_git_repo(path: str) -> bool:
    """
    Return True if path is inside a git repo.
    Use: git rev-parse --git-dir
    Return False (not raise) on non-zero exit.
    """

def init_repo(repo_path: str) -> None:
    """
    - git init --initial-branch=main
    - git lfs install (repo-local)
    - Write .gitattributes:
        *.blend filter=lfs diff=lfs merge=lfs -text
        *.blend1 filter=lfs diff=lfs merge=lfs -text
    - Write .gitignore:
        *.blend1
        __pycache__/
        *.pyc
        .DS_Store
    - git add -A
    - git commit -m "Initialize project"
      (initial commit required so HEAD exists before branching)
    """

def has_uncommitted_changes(repo_path: str) -> bool:
    """
    Return True if working tree is dirty.
    Use: git status --porcelain
    Empty stdout = clean.
    """

def commit(repo_path: str, message: str) -> str:
    """
    Stage everything and commit. Return short hash.
    - git add -A
    - git commit -m message
    Raise RuntimeError if nothing to commit.
    """

def get_current_branch(repo_path: str) -> str | None:
    """
    Return branch name or None if detached HEAD.
    Use: git branch --show-current
    Return None if stdout is empty.
    """

def list_branches(repo_path: str) -> list[dict]:
    """
    Return [{"name": str, "is_current": bool}, ...]
    Use: git branch
    Strip leading "* " to detect current branch.
    """

def create_branch(repo_path: str, name: str) -> None:
    """
    Create and checkout new branch.
    Use: git checkout -b name
    Caller must have sanitized and validated name first.
    """

def checkout(repo_path: str, ref: str) -> None:
    """
    Checkout branch or commit ref.
    RAISE if has_uncommitted_changes() is True — never silently commit here.
    Use: git checkout ref
    After this returns, the caller (operator) must reload the .blend file.
    """

def get_log(repo_path: str, max_count: int = 100) -> list[dict]:
    """
    Return commit history for timeline display.
    Use: git log --all --format="%H|%h|%s|%D|%ct" --max-count=N
    Each entry: {
        "hash": str,
        "short_hash": str,
        "message": str,
        "refs": list[str],   # parsed from %D, e.g. ["HEAD -> main", "origin/main"]
        "timestamp": int,
    }
    Parse %D by splitting on ", " and stripping whitespace.
    """

def sanitize_branch_name(name: str) -> str:
    """
    Pure string function — no subprocess.
    1. Strip leading/trailing whitespace
    2. Replace spaces and slashes with "-"
    3. Strip leading dots, dashes, underscores
    4. Raise ValueError if result is empty
    5. Raise ValueError if result contains: ~ ^ : ? * [ \\ ..
    Return sanitized name.
    """
```

## Error Messages (plain English for non-technical users)

Raise `RuntimeError` with these messages so the operator layer can surface them directly:

- Missing git: `"Git is not installed. Please install it from git-scm.com, then restart Blender."`
- Missing git-lfs: `"Git LFS is not installed. Please install it from git-lfs.com, then restart Blender."`
- Dirty checkout attempt: `"Please save your work before switching branches."`
- Nothing to commit: `"There are no changes to save."`

## Testing

Write tests in `tests/test_git_ops.py` using plain `pytest`. Use `tmp_path` fixtures to create real temporary git repos. Skip LFS tests with `pytest.mark.skipif(shutil.which("git-lfs") is None, reason="git-lfs not installed")`.
