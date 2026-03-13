from __future__ import annotations

import time

from . import constants
from . import timeline_graph
from .git_ops import git_ops
from . import redraw

_cache: dict = {}
_cache_time: float = 0.0
_cache_repo: str = ""

_timeline_cache: dict = {}
_timeline_cache_time: float = 0.0
_timeline_cache_repo: str = ""


def get_git_state(repo_path: str) -> dict:
    global _cache, _cache_time, _cache_repo
    now = time.monotonic()
    if _cache and _cache_repo == repo_path and (now - _cache_time) < constants.CACHE_TTL:
        return _cache

    is_repo = git_ops.is_git_repo(repo_path)
    if is_repo:
        current_branch = git_ops.get_current_branch(repo_path) or "detached HEAD"
        branches = git_ops.list_branches(repo_path)
    else:
        current_branch = ""
        branches = []

    _cache = {"is_repo": is_repo, "current_branch": current_branch, "branches": branches}
    _cache_time = now
    _cache_repo = repo_path
    return _cache


def get_timeline_state(repo_path: str) -> dict:
    global _timeline_cache, _timeline_cache_time, _timeline_cache_repo
    now = time.monotonic()
    if (
        _timeline_cache
        and _timeline_cache_repo == repo_path
        and (now - _timeline_cache_time) < constants.CACHE_TTL
    ):
        return _timeline_cache

    entries = git_ops.get_timeline(repo_path, max_count=constants.GRAPH_MAX_COUNT)
    lineages = git_ops.get_branch_lineages(repo_path, max_count=constants.GRAPH_MAX_COUNT)
    _timeline_cache = timeline_graph.build_timeline_layout(entries, lineages)
    _timeline_cache_time = now
    _timeline_cache_repo = repo_path
    return _timeline_cache


def invalidate_cache() -> None:
    global _cache, _cache_time, _cache_repo
    global _timeline_cache, _timeline_cache_time, _timeline_cache_repo
    _cache = {}
    _cache_time = 0.0
    _cache_repo = ""
    _timeline_cache = {}
    _timeline_cache_time = 0.0
    _timeline_cache_repo = ""
    redraw.tag_view3d_redraw()


def is_repo_cached(repo_path: str) -> bool:
    return get_git_state(repo_path).get("is_repo", False)
