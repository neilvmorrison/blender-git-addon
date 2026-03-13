bl_info = {
    "name": "Blender Git",
    "author": "",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Git",
    "description": "Version control for Blender projects using Git LFS",
    "category": "System",
}

import bpy

from .git_ops import git_ops
from . import properties, operators, panels

# Module-level cache for dependency check — survives window manager resets
_deps: dict[str, bool] = {}


class BlenderGitPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    projects_dir: bpy.props.StringProperty(
        name="Projects Directory",
        description="Root folder where all Git-tracked Blender projects are stored",
        subtype="DIR_PATH",
        default="",
    )

    main_branch_color: bpy.props.FloatVectorProperty(
        name="Main Branch Color",
        description="Color used for the main branch in the timeline",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(0.0, 0.816, 0.6),
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "projects_dir")
        layout.prop(self, "main_branch_color")


def register():
    global _deps
    _deps = git_ops.check_dependencies()

    properties.register()
    bpy.utils.register_class(BlenderGitPreferences)
    operators.register()
    panels.register()


def unregister():
    panels.unregister()
    operators.unregister()
    bpy.utils.unregister_class(BlenderGitPreferences)
    properties.unregister()
