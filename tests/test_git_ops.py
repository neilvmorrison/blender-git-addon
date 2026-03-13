import os
import shutil
import subprocess

import pytest

# Adjust import path so tests can find git_ops regardless of working directory.
import sys

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)

from git_ops import GitOps

skip_no_git = pytest.mark.skipif(
    shutil.which("git") is None, reason="git not installed"
)
skip_no_lfs = pytest.mark.skipif(
    shutil.which("git-lfs") is None, reason="git-lfs not installed"
)


@pytest.fixture
def ops() -> GitOps:
    return GitOps()


@pytest.fixture
def repo(tmp_path: str, ops: GitOps):
    """Create an initialized repo with an initial commit."""
    ops.init_repo(str(tmp_path))
    return str(tmp_path)


# ------------------------------------------------------------------ #
#  check_dependencies
# ------------------------------------------------------------------ #


def test_check_dependencies_returns_dict(ops: GitOps):
    result = ops.check_dependencies()
    assert isinstance(result, dict)
    assert "git" in result
    assert "git_lfs" in result


@skip_no_git
def test_check_dependencies_finds_git(ops: GitOps):
    assert ops.check_dependencies()["git"] is True


@skip_no_lfs
def test_check_dependencies_finds_git_lfs(ops: GitOps):
    assert ops.check_dependencies()["git_lfs"] is True


# ------------------------------------------------------------------ #
#  is_git_repo
# ------------------------------------------------------------------ #


@skip_no_git
def test_is_git_repo_true(repo: str, ops: GitOps):
    assert ops.is_git_repo(repo) is True


@skip_no_git
def test_is_git_repo_false(tmp_path, ops: GitOps):
    assert ops.is_git_repo(str(tmp_path)) is False


# ------------------------------------------------------------------ #
#  init_repo
# ------------------------------------------------------------------ #


@skip_no_git
@skip_no_lfs
def test_init_repo_creates_git_dir(tmp_path, ops: GitOps):
    ops.init_repo(str(tmp_path))
    assert os.path.isdir(os.path.join(str(tmp_path), ".git"))


@skip_no_git
@skip_no_lfs
def test_init_repo_writes_gitattributes(tmp_path, ops: GitOps):
    ops.init_repo(str(tmp_path))
    path = os.path.join(str(tmp_path), ".gitattributes")
    assert os.path.isfile(path)
    contents = open(path).read()
    assert "*.blend filter=lfs" in contents


@skip_no_git
@skip_no_lfs
def test_init_repo_writes_gitignore(tmp_path, ops: GitOps):
    ops.init_repo(str(tmp_path))
    path = os.path.join(str(tmp_path), ".gitignore")
    assert os.path.isfile(path)
    contents = open(path).read()
    assert "*.blend1" in contents
    assert "__pycache__/" in contents


@skip_no_git
@skip_no_lfs
def test_init_repo_creates_initial_commit(tmp_path, ops: GitOps):
    ops.init_repo(str(tmp_path))
    result = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    assert "Initialize project" in result.stdout


@skip_no_git
@skip_no_lfs
def test_init_repo_default_branch_is_main(repo: str, ops: GitOps):
    assert ops.get_current_branch(repo) == "main"


# ------------------------------------------------------------------ #
#  has_uncommitted_changes
# ------------------------------------------------------------------ #


@skip_no_git
@skip_no_lfs
def test_has_uncommitted_changes_clean(repo: str, ops: GitOps):
    assert ops.has_uncommitted_changes(repo) is False


@skip_no_git
@skip_no_lfs
def test_has_uncommitted_changes_dirty(repo: str, ops: GitOps):
    with open(os.path.join(repo, "new.txt"), "w") as f:
        f.write("hello")
    assert ops.has_uncommitted_changes(repo) is True


# ------------------------------------------------------------------ #
#  commit
# ------------------------------------------------------------------ #


@skip_no_git
@skip_no_lfs
def test_commit_returns_short_hash(repo: str, ops: GitOps):
    with open(os.path.join(repo, "file.txt"), "w") as f:
        f.write("content")
    short_hash = ops.commit(repo, "Add file")
    assert len(short_hash) >= 7


@skip_no_git
@skip_no_lfs
def test_commit_nothing_to_commit_raises(repo: str, ops: GitOps):
    with pytest.raises(RuntimeError, match="no changes to save"):
        ops.commit(repo, "Empty")


# ------------------------------------------------------------------ #
#  get_current_branch
# ------------------------------------------------------------------ #


@skip_no_git
@skip_no_lfs
def test_get_current_branch_main(repo: str, ops: GitOps):
    assert ops.get_current_branch(repo) == "main"


@skip_no_git
@skip_no_lfs
def test_get_current_branch_detached(repo: str, ops: GitOps):
    # Detach HEAD by checking out a commit hash directly.
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    commit_hash = result.stdout.strip()
    subprocess.run(
        ["git", "checkout", commit_hash],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert ops.get_current_branch(repo) is None


# ------------------------------------------------------------------ #
#  list_branches
# ------------------------------------------------------------------ #


@skip_no_git
@skip_no_lfs
def test_list_branches_initial(repo: str, ops: GitOps):
    branches = ops.list_branches(repo)
    assert len(branches) == 1
    assert branches[0]["name"] == "main"
    assert branches[0]["is_current"] is True


@skip_no_git
@skip_no_lfs
def test_list_branches_multiple(repo: str, ops: GitOps):
    ops.create_branch(repo, "feature")
    branches = ops.list_branches(repo)
    names = {b["name"] for b in branches}
    assert "main" in names
    assert "feature" in names
    current = [b for b in branches if b["is_current"]]
    assert len(current) == 1
    assert current[0]["name"] == "feature"


# ------------------------------------------------------------------ #
#  create_branch
# ------------------------------------------------------------------ #


@skip_no_git
@skip_no_lfs
def test_create_branch_switches(repo: str, ops: GitOps):
    ops.create_branch(repo, "dev")
    assert ops.get_current_branch(repo) == "dev"


# ------------------------------------------------------------------ #
#  checkout
# ------------------------------------------------------------------ #


@skip_no_git
@skip_no_lfs
def test_checkout_branch(repo: str, ops: GitOps):
    ops.create_branch(repo, "other")
    ops.checkout(repo, "main")
    assert ops.get_current_branch(repo) == "main"


@skip_no_git
@skip_no_lfs
def test_checkout_dirty_raises(repo: str, ops: GitOps):
    ops.create_branch(repo, "other")
    with open(os.path.join(repo, "dirty.txt"), "w") as f:
        f.write("unsaved")
    with pytest.raises(RuntimeError, match="save your work"):
        ops.checkout(repo, "main")


# ------------------------------------------------------------------ #
#  get_log
# ------------------------------------------------------------------ #


@skip_no_git
@skip_no_lfs
def test_get_log_initial(repo: str, ops: GitOps):
    log = ops.get_log(repo)
    assert len(log) == 1
    assert log[0]["message"] == "Initialize project"
    assert isinstance(log[0]["timestamp"], int)
    assert len(log[0]["hash"]) == 40
    assert len(log[0]["short_hash"]) >= 7


@skip_no_git
@skip_no_lfs
def test_get_log_multiple(repo: str, ops: GitOps):
    with open(os.path.join(repo, "a.txt"), "w") as f:
        f.write("a")
    ops.commit(repo, "First")
    with open(os.path.join(repo, "b.txt"), "w") as f:
        f.write("b")
    ops.commit(repo, "Second")
    log = ops.get_log(repo)
    assert len(log) == 3
    assert log[0]["message"] == "Second"
    assert log[1]["message"] == "First"


@skip_no_git
@skip_no_lfs
def test_get_log_empty_repo(tmp_path, ops: GitOps):
    """get_log on an uninitialised dir returns an empty list."""
    subprocess.run(
        ["git", "init", "--initial-branch=main"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    log = ops.get_log(str(tmp_path))
    assert log == []


@skip_no_git
@skip_no_lfs
def test_get_log_refs_parsed(repo: str, ops: GitOps):
    log = ops.get_log(repo)
    # The initial commit on main should have HEAD -> main in refs.
    refs = log[0]["refs"]
    assert any("main" in r for r in refs)


# ------------------------------------------------------------------ #
#  get_timeline
# ------------------------------------------------------------------ #


@skip_no_git
@skip_no_lfs
def test_get_timeline_initial(repo: str, ops: GitOps):
    timeline = ops.get_timeline(repo)
    assert len(timeline) == 1
    assert timeline[0]["message"] == "Initialize project"
    assert timeline[0]["parents"] == []
    assert "main" in timeline[0]["branch_refs"]


@skip_no_git
@skip_no_lfs
def test_get_timeline_includes_parent_hashes(repo: str, ops: GitOps):
    with open(os.path.join(repo, "a.txt"), "w") as f:
        f.write("a")
    first_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    ops.commit(repo, "Second")
    timeline = ops.get_timeline(repo)

    latest = timeline[0]
    assert latest["message"] == "Second"
    assert latest["parents"] == [first_hash]


@skip_no_git
@skip_no_lfs
def test_get_timeline_tracks_local_branch_refs(repo: str, ops: GitOps):
    ops.create_branch(repo, "feature")
    timeline = ops.get_timeline(repo)

    assert "feature" in timeline[0]["branch_refs"]
    assert "main" not in timeline[0]["branch_refs"]


# ------------------------------------------------------------------ #
#  sanitize_branch_name
# ------------------------------------------------------------------ #


def test_sanitize_strips_whitespace(ops: GitOps):
    assert ops.sanitize_branch_name("  feature  ") == "feature"


def test_sanitize_replaces_spaces(ops: GitOps):
    assert ops.sanitize_branch_name("my feature") == "my-feature"


def test_sanitize_replaces_backslashes(ops: GitOps):
    assert ops.sanitize_branch_name("a\\b") == "a-b"


def test_sanitize_removes_forbidden_chars(ops: GitOps):
    assert ops.sanitize_branch_name("feat~1") == "feat1"
    assert ops.sanitize_branch_name("a^b") == "ab"
    assert ops.sanitize_branch_name("a:b") == "ab"
    assert ops.sanitize_branch_name("a?b") == "ab"
    assert ops.sanitize_branch_name("a*b") == "ab"
    assert ops.sanitize_branch_name("a[b]c") == "abc"


def test_sanitize_collapses_dots(ops: GitOps):
    assert ops.sanitize_branch_name("a..b") == "a.b"


def test_sanitize_strips_leading_special(ops: GitOps):
    assert ops.sanitize_branch_name(".feature") == "feature"
    assert ops.sanitize_branch_name("-feature") == "feature"
    assert ops.sanitize_branch_name("_feature") == "feature"


def test_sanitize_strips_lock_suffix(ops: GitOps):
    assert ops.sanitize_branch_name("branch.lock") == "branch"


def test_sanitize_strips_trailing_dot_dash(ops: GitOps):
    assert ops.sanitize_branch_name("branch.") == "branch"
    assert ops.sanitize_branch_name("branch-") == "branch"


def test_sanitize_collapses_dashes(ops: GitOps):
    assert ops.sanitize_branch_name("a--b") == "a-b"


def test_sanitize_empty_raises(ops: GitOps):
    with pytest.raises(RuntimeError, match="valid branch name"):
        ops.sanitize_branch_name("   ")


def test_sanitize_all_forbidden_raises(ops: GitOps):
    with pytest.raises(RuntimeError, match="valid branch name"):
        ops.sanitize_branch_name("~^:?*")


# ------------------------------------------------------------------ #
#  Module-level convenience instance
# ------------------------------------------------------------------ #


def test_module_level_instance():
    from git_ops import git_ops

    assert isinstance(git_ops, GitOps)
