import os

import bpy

from .git_ops import git_ops


class GitInitRepo(bpy.types.Operator):
    bl_idname = "git.init_repo"
    bl_label = "Initialize Project"
    bl_description = "Set up version control for this Blender project"

    @classmethod
    def poll(cls, context):
        if not bpy.data.filepath:
            return False
        return not git_ops.is_git_repo(os.path.dirname(bpy.data.filepath))

    def execute(self, context):
        try:
            bpy.ops.wm.save_mainfile()
            repo_path = os.path.dirname(bpy.data.filepath)
            git_ops.init_repo(repo_path)
        except RuntimeError as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}
        self.report({"INFO"}, "Project initialized")
        return {"FINISHED"}


class GitCommit(bpy.types.Operator):
    bl_idname = "git.commit"
    bl_label = "Commit"
    bl_description = "Save a version of your project"

    @classmethod
    def poll(cls, context):
        if not bpy.data.filepath:
            return False
        return git_ops.is_git_repo(os.path.dirname(bpy.data.filepath))

    def execute(self, context):
        try:
            bpy.ops.wm.save_mainfile()
            wm = context.window_manager
            repo_path = os.path.dirname(bpy.data.filepath)
            message = wm.git_commit_message
            short_hash = git_ops.commit(repo_path, message)
        except RuntimeError as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}
        wm.git_show_commit_input = False
        wm.git_commit_message = "Save progress"
        self.report({"INFO"}, f"Version saved ({short_hash})")
        return {"FINISHED"}


class GitCreateBranch(bpy.types.Operator):
    bl_idname = "git.create_branch"
    bl_label = "Create Branch"
    bl_description = "Create a new branch"

    @classmethod
    def poll(cls, context):
        if not bpy.data.filepath:
            return False
        return git_ops.is_git_repo(os.path.dirname(bpy.data.filepath))

    def execute(self, context):
        try:
            wm = context.window_manager
            repo_path = os.path.dirname(bpy.data.filepath)
            name = wm.git_branch_name
            sanitized = git_ops.sanitize_branch_name(name)
            git_ops.create_branch(repo_path, sanitized)
        except RuntimeError as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}
        wm.git_show_branch_input = False
        wm.git_branch_name = ""
        self.report({"INFO"}, f"Branch '{sanitized}' created")
        return {"FINISHED"}


class GitCheckoutBranch(bpy.types.Operator):
    bl_idname = "git.checkout_branch"
    bl_label = "Switch Branch"
    bl_description = "Switch to a different branch"

    ref: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        if not bpy.data.filepath:
            return False
        return git_ops.is_git_repo(os.path.dirname(bpy.data.filepath))

    def execute(self, context):
        try:
            repo_path = os.path.dirname(bpy.data.filepath)

            # Auto-commit dirty working tree before checkout
            if git_ops.has_uncommitted_changes(repo_path):
                bpy.ops.wm.save_mainfile()
                git_ops.commit(repo_path, "Auto-save before switching branches")

            git_ops.checkout(repo_path, self.ref)
        except RuntimeError as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}

        # Reload the .blend file so LFS serves the correct binary
        bpy.ops.wm.open_mainfile(filepath=bpy.data.filepath)
        return {"FINISHED"}


class GitToggleCommitInput(bpy.types.Operator):
    bl_idname = "git.toggle_commit_input"
    bl_label = "Toggle Commit Input"

    def execute(self, context):
        wm = context.window_manager
        wm.git_show_commit_input = not wm.git_show_commit_input
        if not wm.git_show_commit_input:
            wm.git_commit_message = "Save progress"
        return {"FINISHED"}


class GitToggleBranchInput(bpy.types.Operator):
    bl_idname = "git.toggle_branch_input"
    bl_label = "Toggle Branch Input"

    def execute(self, context):
        wm = context.window_manager
        wm.git_show_branch_input = not wm.git_show_branch_input
        if not wm.git_show_branch_input:
            wm.git_branch_name = ""
        return {"FINISHED"}


classes = [
    GitInitRepo,
    GitCommit,
    GitCreateBranch,
    GitCheckoutBranch,
    GitToggleCommitInput,
    GitToggleBranchInput,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
