---
name: blender-agent
description: Use this agent to implement or modify operators.py and panels.py — the Blender UI layer. Invoke for tasks involving operator logic, panel layout, draw functions, state-conditional UI, the timeline panel, branch switching, commit UI, or the file-reload-after-checkout flow.
---

You are implementing the Blender UI layer for a git version-control addon. Your files are `operators.py` and `panels.py`. These depend on `git_ops.py` being implemented first.

Read `CLAUDE.md`, `.claude/docs/gui.md`, and `.claude/docs/git.md` before writing any code.

## Critical Invariants

1. **Never checkout with dirty working tree** — always check `git_ops.has_uncommitted_changes()` before any `git_ops.checkout()` call. If dirty, either auto-commit (with user's current commit message) or abort with a clear message.
2. **Always reload `.blend` after checkout** — after any `git_ops.checkout()` returns, call `bpy.ops.wm.open_mainfile(filepath=bpy.data.filepath)`. This is non-negotiable: LFS won't serve the correct binary until the file is reopened.
3. **Only show valid actions** — use `poll()` on operators and conditional `layout` rendering in panels to hide actions that can't currently be performed.

## `operators.py`

Each operator follows this pattern:
```python
class GitInitRepo(bpy.types.Operator):
    bl_idname = "git.init_repo"
    bl_label = "Initialize Project"
    bl_description = "Set up version control for this Blender project"

    @classmethod
    def poll(cls, context):
        # Return False to grey-out/hide the operator
        return bool(bpy.data.filepath)  # file must be saved first

    def execute(self, context):
        try:
            git_ops.init_repo(os.path.dirname(bpy.data.filepath))
        except RuntimeError as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}
        return {"FINISHED"}
```

### Required Operators

| bl_idname | Action | poll condition |
|---|---|---|
| `git.init_repo` | Initialize repo in file's directory | file is saved, not already a repo |
| `git.commit` | Stage all + commit with message from `wm.git_commit_message` | repo initialized, file saved |
| `git.create_branch` | Create branch named `wm.git_branch_name` | repo initialized |
| `git.checkout_branch` | Checkout branch (ref passed via property) | repo initialized, clean or auto-commit |
| `git.toggle_commit_input` | Toggle `wm.git_show_commit_input` | always |
| `git.toggle_branch_input` | Toggle `wm.git_show_branch_input` | always |

For `git.checkout_branch`, use an operator string property to pass the target ref:
```python
ref: bpy.props.StringProperty()  # set by the panel when drawing branch buttons
```

After `git.checkout_branch` succeeds:
```python
bpy.ops.wm.open_mainfile(filepath=bpy.data.filepath)
```

Use `self.report({"ERROR"}, message)` for all errors — never raise exceptions out of `execute()`.

## `panels.py`

### Main Sidebar Panel

```python
class GIT_PT_main(bpy.types.Panel):
    bl_label = "Git"
    bl_idname = "GIT_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Git"
```

### Draw Logic (state machine)

```python
def draw(self, context):
    layout = self.layout
    wm = context.window_manager

    # 1. Dependency check — show install prompt if git/git-lfs missing
    if not wm.git_deps_ok:
        if wm.git_missing == "git":
            layout.label(text="Git is not installed.", icon="ERROR")
            layout.label(text="Install from git-scm.com")
        else:
            layout.label(text="Git LFS is not installed.", icon="ERROR")
            layout.label(text="Install from git-lfs.com")
        layout.label(text="Then restart Blender.")
        return

    # 2. No file open
    if not bpy.data.filepath:
        layout.label(text="Save your file first.", icon="INFO")
        return

    repo_path = os.path.dirname(bpy.data.filepath)

    # 3. Not yet a git repo
    if not git_ops.is_git_repo(repo_path):
        layout.operator("git.init_repo", icon="ADD")
        return

    # 4. Initialized — show full UI
    branch = git_ops.get_current_branch(repo_path) or "detached HEAD"
    layout.label(text=f"Branch: {branch}", icon="NONE")

    # Commit section
    row = layout.row()
    row.operator("git.toggle_commit_input",
                 text="Save Version" if not wm.git_show_commit_input else "Cancel",
                 icon="FILE_TICK")
    if wm.git_show_commit_input:
        layout.prop(wm, "git_commit_message", text="")
        layout.operator("git.commit", text="Commit")

    layout.separator()

    # Branch section
    row = layout.row()
    row.operator("git.toggle_branch_input",
                 text="New Branch" if not wm.git_show_branch_input else "Cancel",
                 icon="PLUS")
    if wm.git_show_branch_input:
        layout.prop(wm, "git_branch_name", text="")
        layout.operator("git.create_branch", text="Create Branch")

    layout.separator()

    # Branch switcher
    layout.label(text="Switch Branch:")
    branches = git_ops.list_branches(repo_path)
    for b in branches:
        row = layout.row()
        icon = "LAYER_ACTIVE" if b["is_current"] else "LAYER_USED"
        op = row.operator("git.checkout_branch", text=b["name"], icon=icon)
        op.ref = b["name"]
```

### Timeline Panel

```python
class GIT_PT_timeline(bpy.types.Panel):
    bl_label = "Git Timeline"
    bl_idname = "GIT_PT_timeline"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Git"
    bl_options = {"DEFAULT_CLOSED"}
```

Draw the commit log returned by `git_ops.get_log()`. Each row shows short hash, message, and branch refs. Use `layout.box()` per commit. Scroll is handled automatically by Blender's UI region when content overflows.

Color the main branch label using the `main_branch_color` from addon preferences:
```python
prefs = context.preferences.addons[__package__].preferences
# Use prefs.main_branch_color (float RGB) to tint the label row
row.alert = False  # can't set arbitrary color on labels; use icon tinting or just bold
```
Note: Blender's panel UI doesn't support arbitrary label colors — use an icon or `layout.alert = True` to highlight the main branch row as a visual distinction.

## `register()` / `unregister()` in `panels.py` and `operators.py`

Each file must define:
```python
classes = [GitInitRepo, GitCommit, ...]  # all classes in this module

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
```
