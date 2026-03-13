import os

import bpy

from .git_ops import git_ops


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

        # State 2: No file saved
        if not bpy.data.filepath:
            layout.label(text="Save your file first.", icon="INFO")
            return

        repo_path = os.path.dirname(bpy.data.filepath)

        # State 3: Not a git repo
        if not git_ops.is_git_repo(repo_path):
            layout.operator("git.init_repo", icon="ADD")
            return

        # State 4: Initialized — full UI
        branch = git_ops.get_current_branch(repo_path) or "detached HEAD"
        layout.label(text=f"Branch: {branch}")

        # Commit section
        layout.separator()
        row = layout.row()
        row.operator(
            "git.toggle_commit_input",
            text="Save Version" if not wm.git_show_commit_input else "Cancel",
            icon="FILE_TICK",
        )
        if wm.git_show_commit_input:
            layout.prop(wm, "git_commit_message", text="")
            layout.operator("git.commit", text="Commit", icon="CHECKMARK")

        # Branch creation section
        layout.separator()
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

        # Branch switcher section
        layout.separator()
        layout.label(text="Branches:")
        branches = git_ops.list_branches(repo_path)
        for b in branches:
            row = layout.row()
            icon = "RADIOBUT_ON" if b["is_current"] else "RADIOBUT_OFF"
            op = row.operator("git.checkout_branch", text=b["name"], icon=icon)
            op.ref = b["name"]
            row.enabled = not b["is_current"]


classes = [GIT_PT_main]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
