import os
import re
import shutil

import bpy

from .git_ops import git_ops
from .panels import (
    clear_timeline_mouse,
    ensure_timeline_handler,
    handle_timeline_event,
    invalidate_cache,
    is_repo_cached,
    remove_timeline_handler,
    tag_view3d_redraw,
)


def _derive_project_name(filepath: str) -> str:
    """Return a filesystem-safe project name derived from a .blend filepath."""
    if filepath:
        name = os.path.splitext(os.path.basename(filepath))[0]
    else:
        name = "untitled"
    name = re.sub(r"[\s\\]+", "-", name.strip())
    name = re.sub(r"[~^:?*\[\]<>|\"]+", "", name)
    name = name.strip(".-_")
    name = re.sub(r"-{2,}", "-", name)
    return name or "untitled"


def _get_projects_dir(context) -> str:
    """Return the configured projects directory, or empty string if not set."""
    prefs = context.preferences.addons.get("blender-git")
    if not prefs:
        return ""
    return prefs.preferences.projects_dir or ""


class GitOpenPreferences(bpy.types.Operator):
    bl_idname = "git.open_preferences"
    bl_label = "Open Addon Preferences"
    bl_description = "Open addon preferences to set your Projects Directory"

    def execute(self, context):
        bpy.ops.preferences.addon_show(module="blender-git")
        return {"FINISHED"}


class GitInitRepo(bpy.types.Operator):
    bl_idname = "git.init_repo"
    bl_label = "Initialize Project"
    bl_description = "Set up version control for this Blender project"

    project_name: bpy.props.StringProperty(
        name="Project Name",
        description="Name for the project directory",
        default="",
    )

    @classmethod
    def poll(cls, context):
        from . import _deps
        if not _deps.get("git") or not _deps.get("git_lfs"):
            return False
        if not _get_projects_dir(context):
            return False
        if bpy.data.filepath:
            return not is_repo_cached(os.path.dirname(bpy.data.filepath))
        return True

    def invoke(self, context, event):
        self.project_name = _derive_project_name(bpy.data.filepath)
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "project_name")

    def execute(self, context):
        projects_dir = os.path.normpath(_get_projects_dir(context))
        name = _derive_project_name(self.project_name) if self.project_name else "untitled"

        filepath = bpy.data.filepath
        norm_filepath_dir = os.path.normpath(os.path.dirname(filepath)) if filepath else None

        # Check if file is already in a project subdirectory under projects_dir
        already_under = (
            norm_filepath_dir is not None
            and norm_filepath_dir.startswith(projects_dir + os.sep)
        )

        if already_under:
            target_dir = norm_filepath_dir
            new_dir_created = False
        else:
            # Compute target_dir, handling collisions
            target_dir = os.path.join(projects_dir, name)
            if os.path.exists(target_dir):
                suffix = 2
                while os.path.exists(f"{target_dir}-{suffix}"):
                    suffix += 1
                target_dir = f"{target_dir}-{suffix}"
            new_dir_created = True

        try:
            if new_dir_created:
                os.makedirs(target_dir)

            if not filepath:
                # Case 1: Unsaved file — save into the new project dir
                blend_path = os.path.join(target_dir, name + ".blend")
                bpy.ops.wm.save_as_mainfile(filepath=blend_path)

            elif already_under:
                # Case 2b: Already under projects_dir — init in place
                bpy.ops.wm.save_mainfile()

            else:
                # Case 2: Saved file elsewhere — copy to new project dir
                bpy.ops.wm.save_mainfile()
                dst = os.path.join(target_dir, os.path.basename(filepath))
                shutil.copy2(filepath, dst)

                git_ops.init_repo(target_dir)
                invalidate_cache()

                dst_path = dst
                bpy.app.timers.register(
                    lambda: bpy.ops.git.confirm_open("INVOKE_DEFAULT", filepath=dst_path) and None,
                    first_interval=0.05,
                )
                return {"FINISHED"}

            git_ops.init_repo(target_dir)

        except (OSError, RuntimeError) as e:
            self.report({"ERROR"}, str(e))
            if new_dir_created and os.path.exists(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)
            return {"CANCELLED"}

        invalidate_cache()
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
        return is_repo_cached(os.path.dirname(bpy.data.filepath))

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
        invalidate_cache()
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
        return is_repo_cached(os.path.dirname(bpy.data.filepath))

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
        invalidate_cache()
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
        return is_repo_cached(os.path.dirname(bpy.data.filepath))

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

        invalidate_cache()

        # Reload the .blend file so LFS serves the correct binary
        bpy.ops.wm.open_mainfile(filepath=bpy.data.filepath)
        return {"FINISHED"}


class GitConfirmOpen(bpy.types.Operator):
    bl_idname = "git.confirm_open"
    bl_label = "Open New Project?"
    bl_description = "Open the newly initialized project file"

    filepath: bpy.props.StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        bpy.ops.wm.open_mainfile(filepath=self.filepath)
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


class GitTimelineModal(bpy.types.Operator):
    bl_idname = "git.timeline_modal"
    bl_label = "Git Timeline Interaction"

    _is_running = False

    def invoke(self, context, event):
        if GitTimelineModal._is_running:
            return {"CANCELLED"}
        GitTimelineModal._is_running = True
        ensure_timeline_handler()
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if (
            not context.window_manager.git_timeline_visible
            or not bpy.data.filepath
            or not is_repo_cached(os.path.dirname(bpy.data.filepath))
        ):
            clear_timeline_mouse()
            remove_timeline_handler()
            GitTimelineModal._is_running = False
            return {"CANCELLED"}

        if handle_timeline_event(context, event):
            return {"RUNNING_MODAL"}
        if event.type == "ESC":
            context.window_manager.git_timeline_visible = False
            clear_timeline_mouse()
            remove_timeline_handler()
            GitTimelineModal._is_running = False
            return {"CANCELLED"}
        return {"PASS_THROUGH"}


class GitToggleTimeline(bpy.types.Operator):
    bl_idname = "git.toggle_timeline"
    bl_label = "Toggle Timeline"
    bl_description = "Show or hide the git timeline overlay"

    @classmethod
    def poll(cls, context):
        if not bpy.data.filepath:
            return False
        return is_repo_cached(os.path.dirname(bpy.data.filepath))

    def execute(self, context):
        wm = context.window_manager
        wm.git_timeline_visible = not wm.git_timeline_visible
        wm.git_timeline_scroll = 0.0
        wm.git_timeline_hover_hash = ""

        if wm.git_timeline_visible:
            bpy.ops.git.timeline_modal("INVOKE_DEFAULT")
        else:
            clear_timeline_mouse()
            remove_timeline_handler()
            tag_view3d_redraw()
        return {"FINISHED"}


class GitResetTimelinePosition(bpy.types.Operator):
    bl_idname = "git.reset_timeline_position"
    bl_label = "Reset Timeline Position"
    bl_description = "Reset timeline to its default position next to the Git panel"

    @classmethod
    def poll(cls, context):
        if not bpy.data.filepath:
            return False
        return is_repo_cached(os.path.dirname(bpy.data.filepath))

    def execute(self, context):
        wm = context.window_manager
        wm.git_timeline_offset_x = 0.0
        wm.git_timeline_offset_y = 0.0
        tag_view3d_redraw()
        return {"FINISHED"}


class GitCycleTimelineOrder(bpy.types.Operator):
    bl_idname = "git.cycle_timeline_order"
    bl_label = "Cycle Timeline Order"
    bl_description = "Switch between top-down and bottom-up commit ordering"

    @classmethod
    def poll(cls, context):
        if not bpy.data.filepath:
            return False
        return is_repo_cached(os.path.dirname(bpy.data.filepath))

    def execute(self, context):
        wm = context.window_manager
        wm.git_timeline_order = (
            "TOP_DOWN"
            if wm.git_timeline_order == "BOTTOM_UP"
            else "BOTTOM_UP"
        )
        wm.git_timeline_scroll = 0.0
        wm.git_timeline_hover_hash = ""
        tag_view3d_redraw()
        return {"FINISHED"}


classes = [
    GitOpenPreferences,
    GitInitRepo,
    GitConfirmOpen,
    GitCommit,
    GitCreateBranch,
    GitCheckoutBranch,
    GitToggleCommitInput,
    GitToggleBranchInput,
    GitTimelineModal,
    GitToggleTimeline,
    GitResetTimelinePosition,
    GitCycleTimelineOrder,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
