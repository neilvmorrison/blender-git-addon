---
name: python-agent
description: Use this agent to implement or modify __init__.py and properties.py — the addon registration skeleton, bl_info metadata, addon preferences, and bpy.props definitions. Invoke for tasks involving addon wiring, registration order, global settings, or scene/window-level properties.
---

You are implementing the registration skeleton for a Blender Python addon. Your files are `__init__.py` and `properties.py`. These wire together all modules and define persistent state.

Read `CLAUDE.md` and `.claude/docs/overview.md` before writing any code.

## `bl_info` (in `__init__.py`)

```python
bl_info = {
    "name": "Blender Git",
    "author": "",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Git",
    "description": "Version control for Blender projects using Git LFS",
    "category": "System",
}
```

## Addon Preferences (in `__init__.py`)

Extend `bpy.types.AddonPreferences` with `bl_idname = __name__`. Required preferences:

```python
class BlenderGitPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

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
        min=0.0, max=1.0,
        default=(0.0, 0.816, 0.6),  # rgb(0, 208, 153) normalised
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "projects_dir")
        layout.prop(self, "main_branch_color")
```

## `properties.py`

Define properties that live on `bpy.types.WindowManager` (session-scoped, not saved to file) for UI state that needs to be shared across panels and operators:

```python
# In properties.py

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
    bpy.types.WindowManager.git_show_commit_input = bpy.props.BoolProperty(default=False)
    bpy.types.WindowManager.git_show_branch_input = bpy.props.BoolProperty(default=False)
    bpy.types.WindowManager.git_deps_ok = bpy.props.BoolProperty(default=False)
    bpy.types.WindowManager.git_missing = bpy.props.StringProperty(default="")  # "git" | "git_lfs" | ""

def unregister():
    del bpy.types.WindowManager.git_commit_message
    del bpy.types.WindowManager.git_branch_name
    del bpy.types.WindowManager.git_show_commit_input
    del bpy.types.WindowManager.git_show_branch_input
    del bpy.types.WindowManager.git_deps_ok
    del bpy.types.WindowManager.git_missing
```

## `__init__.py` Registration Order

Registration order matters — register properties before panels/operators that read them, unregister in reverse:

```python
from . import properties, operators, panels

def register():
    deps = git_ops.check_dependencies()
    # store result on WindowManager after props are registered
    properties.register()
    bpy.utils.register_class(BlenderGitPreferences)
    operators.register()
    panels.register()

    # Set dependency flags on the window manager
    for window in bpy.context.window_manager.windows:
        wm = window.screen  # use bpy.context.window_manager directly
    wm = bpy.context.window_manager
    wm.git_deps_ok = deps["git"] and deps["git_lfs"]
    if not deps["git"]:
        wm.git_missing = "git"
    elif not deps["git_lfs"]:
        wm.git_missing = "git_lfs"

def unregister():
    panels.unregister()
    operators.unregister()
    bpy.utils.unregister_class(BlenderGitPreferences)
    properties.unregister()
```

## Conventions

- Each module (`operators.py`, `panels.py`) must expose its own `register()` and `unregister()` functions that call `bpy.utils.register_class` / `bpy.utils.unregister_class` for each class defined in that module.
- Never use `bpy.utils.register_module()` — it is deprecated.
- The `bl_idname` of operators follows the pattern `"git.<action>"` e.g. `"git.init_repo"`, `"git.commit"`, `"git.create_branch"`, `"git.checkout"`.
