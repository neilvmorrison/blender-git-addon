import bpy


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


def unregister():
    del bpy.types.WindowManager.git_show_branch_input
    del bpy.types.WindowManager.git_show_commit_input
    del bpy.types.WindowManager.git_branch_name
    del bpy.types.WindowManager.git_commit_message
