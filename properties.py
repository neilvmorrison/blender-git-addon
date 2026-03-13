import os

import bpy


def _branch_items(self, context):
    """Dynamic item list for the branch dropdown."""
    if not bpy.data.filepath:
        return [("__none__", "No branches", "")]
    from .panels import _get_git_state
    repo_path = os.path.dirname(bpy.data.filepath)
    state = _get_git_state(repo_path)
    branches = state.get("branches", [])
    if not branches:
        return [("__none__", "No branches", "")]
    return [(b["name"], b["name"], "") for b in branches]


def _on_branch_change(self, context):
    """Trigger checkout when the user picks a different branch from the dropdown."""
    new_branch = self.git_active_branch
    if not bpy.data.filepath or new_branch in ("__none__", ""):
        return
    repo_path = os.path.dirname(bpy.data.filepath)
    from .panels import _get_git_state
    state = _get_git_state(repo_path)
    if new_branch == state.get("current_branch"):
        return
    bpy.ops.git.checkout_branch(ref=new_branch)


def register():
    bpy.types.WindowManager.git_commit_message = bpy.props.StringProperty(
        name="Commit Message",
        default="Save progress",
    )
    bpy.types.WindowManager.git_branch_name = bpy.props.StringProperty(
        name="Branch Name",
        default="",
    )
    bpy.types.WindowManager.git_show_commit_input = bpy.props.BoolProperty(
        default=False,
    )
    bpy.types.WindowManager.git_show_branch_input = bpy.props.BoolProperty(
        default=False,
    )
    bpy.types.WindowManager.git_active_branch = bpy.props.EnumProperty(
        name="Branch",
        items=_branch_items,
        update=_on_branch_change,
    )


def unregister():
    del bpy.types.WindowManager.git_active_branch
    del bpy.types.WindowManager.git_show_branch_input
    del bpy.types.WindowManager.git_show_commit_input
    del bpy.types.WindowManager.git_branch_name
    del bpy.types.WindowManager.git_commit_message
