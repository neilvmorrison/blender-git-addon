import os
import time

import bpy

from .git_ops import git_ops

# ---------------------------------------------------------------------------
# Git state cache — avoids spawning subprocesses on every panel redraw / poll
# ---------------------------------------------------------------------------

_cache: dict = {}
_cache_time: float = 0.0
_cache_repo: str = ""
_CACHE_TTL: float = 2.0  # seconds


def _get_git_state(repo_path: str) -> dict:
    """Return cached git state for *repo_path*, refreshing at most every 2 s."""
    global _cache, _cache_time, _cache_repo

    now = time.monotonic()
    if (
        _cache
        and _cache_repo == repo_path
        and (now - _cache_time) < _CACHE_TTL
    ):
        return _cache

    is_repo = git_ops.is_git_repo(repo_path)
    if is_repo:
        current_branch = git_ops.get_current_branch(repo_path) or "detached HEAD"
        branches = git_ops.list_branches(repo_path)
    else:
        current_branch = ""
        branches = []

    _cache = {
        "is_repo": is_repo,
        "current_branch": current_branch,
        "branches": branches,
    }
    _cache_time = now
    _cache_repo = repo_path
    return _cache


def invalidate_cache() -> None:
    """Force the next ``_get_git_state`` call to re-query git.

    Call this from operators that mutate git state (init, commit, branch,
    checkout).
    """
    global _cache, _cache_time, _cache_repo
    _cache = {}
    _cache_time = 0.0
    _cache_repo = ""


def is_repo_cached(repo_path: str) -> bool:
    """Lightweight check used by operator ``poll()`` methods."""
    return _get_git_state(repo_path).get("is_repo", False)


def _get_deps() -> dict[str, bool]:
    """Read the module-level dependency cache from the package."""
    from . import _deps
    return _deps


class GIT_PT_main(bpy.types.Panel):
    bl_label = "Git"
    bl_idname = "GIT_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Git"

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

        # State 1: Dependencies missing
        deps = _get_deps()
        if not deps.get("git"):
            layout.label(text="Git is not installed.", icon="ERROR")
            layout.label(text="Install from git-scm.com")
            layout.label(text="Then restart Blender.")
            return
        if not deps.get("git_lfs"):
            layout.label(text="Git LFS is not installed.", icon="ERROR")
            layout.label(text="Install from git-lfs.com")
            layout.label(text="Then restart Blender.")
            return

        # State 2: No projects directory configured
        prefs = context.preferences.addons.get("blender-git")
        projects_dir = prefs.preferences.projects_dir if prefs else ""
        if not projects_dir:
            layout.label(text="Set a Projects Directory:", icon="INFO")
            layout.operator("git.open_preferences", text="Open Preferences", icon="PREFERENCES")
            return

        # State 3: No file saved — can still initialize (will save into projects_dir)
        if not bpy.data.filepath:
            layout.operator("git.init_repo", icon="ADD")
            return

        repo_path = os.path.dirname(bpy.data.filepath)

        # Use cached git state to avoid subprocess calls on every redraw
        state = _get_git_state(repo_path)

        # State 4: Not a git repo
        if not state["is_repo"]:
            layout.operator("git.init_repo", icon="ADD")
            return

        # Branch switcher section — keep dropdown in sync with actual git state
        if wm.git_active_branch != state["current_branch"]:
            wm.git_active_branch = state["current_branch"]

        layout.separator()
        layout.prop(wm, "git_active_branch", text="Branch")
        row = layout.row()
        row.operator(
            "git.toggle_branch_input",
            text="New Branch" if not wm.git_show_branch_input else "Cancel",
            icon="PLUS",
        )
        if wm.git_show_branch_input:
            layout.prop(wm, "git_branch_name", text="")
            layout.operator(
                "git.create_branch", text="Create Branch", icon="CHECKMARK"
            )

        # Commit section
        layout.separator()
        row = layout.row()
        row.operator(
            "git.toggle_commit_input",
            text="Create Commit" if not wm.git_show_commit_input else "Cancel",
            icon="FILE_TICK",
        )
        if wm.git_show_commit_input:
            layout.prop(wm, "git_commit_message", text="")
            layout.operator("git.commit", text="Commit", icon="CHECKMARK")


classes = [GIT_PT_main]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
