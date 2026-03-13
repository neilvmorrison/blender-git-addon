"""Git addon panels and re-exports for operators."""

from __future__ import annotations

import os

import bpy

from .lib import git_cache
from .timeline import overlay as timeline_overlay

invalidate_cache = git_cache.invalidate_cache
is_repo_cached = git_cache.is_repo_cached
clear_timeline_mouse = timeline_overlay.clear_timeline_mouse
ensure_timeline_handler = timeline_overlay.ensure_timeline_handler
handle_timeline_event = timeline_overlay.handle_timeline_event
remove_timeline_handler = timeline_overlay.remove_timeline_handler
tag_view3d_redraw = timeline_overlay.tag_view3d_redraw


def _get_deps() -> dict[str, bool]:
    from . import _deps
    return _deps


def _get_git_state(repo_path: str) -> dict:
    return git_cache.get_git_state(repo_path)


class GIT_PT_main(bpy.types.Panel):
    bl_label = "Git"
    bl_idname = "GIT_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Git"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        wm = context.window_manager

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

        prefs = context.preferences.addons.get("blender-git")
        projects_dir = prefs.preferences.projects_dir if prefs else ""
        if not projects_dir:
            layout.label(text="Set a Projects Directory:", icon="INFO")
            layout.operator(
                "git.open_preferences",
                text="Open Preferences",
                icon="PREFERENCES",
            )
            return

        if not bpy.data.filepath:
            layout.operator("git.init_repo", icon="ADD")
            return

        repo_path = os.path.dirname(bpy.data.filepath)
        state = _get_git_state(repo_path)
        if not state["is_repo"]:
            layout.operator("git.init_repo", icon="ADD")
            return

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
                "git.create_branch",
                text="Create Branch",
                icon="CHECKMARK",
            )

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

        layout.separator()
        timeline_box = layout.box()
        timeline_box.label(text="Timeline")
        row = timeline_box.row(align=True)
        row.operator(
            "git.toggle_timeline",
            text="Hide Timeline" if wm.git_timeline_visible else "Show Timeline",
            icon="HIDE_OFF" if wm.git_timeline_visible else "GRAPH",
        )
        row.operator(
            "git.cycle_timeline_order",
            text="Bottom-Up" if wm.git_timeline_order == "BOTTOM_UP" else "Top-Down",
            icon="SORTTIME",
        )
        row.operator("git.reset_timeline_position", text="", icon="LOOP_BACK")
        if wm.git_timeline_visible:
            timeline_box.label(text="Drag header to move. Scroll to browse.")


classes = [GIT_PT_main]


def register() -> None:
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister() -> None:
    timeline_overlay.remove_timeline_handler()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
