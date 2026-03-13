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
    bpy.types.WindowManager.git_timeline_visible = bpy.props.BoolProperty(
        name="Show Timeline",
        default=False,
    )
    bpy.types.WindowManager.git_timeline_order = bpy.props.EnumProperty(
        name="Timeline Order",
        items=(
            ("BOTTOM_UP", "Bottom-Up", "Show newest commits at the bottom"),
            ("TOP_DOWN", "Top-Down", "Show newest commits at the top"),
        ),
        default="BOTTOM_UP",
    )
    bpy.types.WindowManager.git_timeline_scroll = bpy.props.FloatProperty(
        name="Timeline Scroll",
        default=0.0,
        min=0.0,
    )
    bpy.types.WindowManager.git_timeline_hover_hash = bpy.props.StringProperty(
        name="Timeline Hover Commit",
        default="",
    )
    bpy.types.WindowManager.git_timeline_offset_x = bpy.props.FloatProperty(
        name="Timeline Offset X",
        default=0.0,
        description="Horizontal offset from default position (drag header to move)",
    )
    bpy.types.WindowManager.git_timeline_offset_y = bpy.props.FloatProperty(
        name="Timeline Offset Y",
        default=0.0,
        description="Vertical offset from default position (drag header to move)",
    )


def unregister():
    del bpy.types.WindowManager.git_timeline_offset_y
    del bpy.types.WindowManager.git_timeline_offset_x
    del bpy.types.WindowManager.git_timeline_hover_hash
    del bpy.types.WindowManager.git_timeline_scroll
    del bpy.types.WindowManager.git_timeline_order
    del bpy.types.WindowManager.git_timeline_visible
    del bpy.types.WindowManager.git_active_branch
    del bpy.types.WindowManager.git_show_branch_input
    del bpy.types.WindowManager.git_show_commit_input
    del bpy.types.WindowManager.git_branch_name
    del bpy.types.WindowManager.git_commit_message
