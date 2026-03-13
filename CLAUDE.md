# Blender Git Addon — CLAUDE.md

## What This Is

A Blender Python addon that provides a GUI for version-controlling Blender project files using Git LFS (Large File Storage). Targeted at non-technical Blender users who want the safety of version control without needing to understand git.

## Project Structure (Target)

```
blender-git/
├── __init__.py          # Addon registration, bl_info, preferences class
├── operators.py         # bpy.types.Operator subclasses (all user actions)
├── panels.py            # bpy.types.Panel subclasses (sidebar + timeline UI)
├── git_ops.py           # All git/LFS subprocess calls — no bpy dependency
├── properties.py        # bpy.props definitions stored on the scene/window
└── .claude/docs/        # Design docs — read these before implementing anything
```

## Available Agents & Skills

### Code Refactoring Agent

- **Location**: `.claude/agents/refactor_skill.py`
- **Capability**: Refactor Python code with DRY principles, type hints, and industry best practices
- **When to use**:
  - User asks "refactor this code"
  - You notice duplicated patterns
  - Code lacks type hints or docstrings
- **Safety**: Always presents changes for review before applying

### How to trigger

User can say: "Use the refactoring skill on src/data.py to reduce duplication"

## Blender Addon Conventions

- Every class that uses `bpy` must be registered via `bpy.utils.register_class()` in `register()` and unregistered in `unregister()` — both called in `__init__.py`.
- `bl_info` dict in `__init__.py` controls addon metadata visible in Blender preferences.
- Operators use `bl_idname`, `bl_label`, and implement `execute(self, context)` returning `{'FINISHED'}` or `{'CANCELLED'}`.
- Panels use `bl_space_type`, `bl_region_type`, `bl_category`, and implement `draw(self, context)`.
- Addon preferences extend `bpy.types.AddonPreferences` — use this for the global working directory setting.
- Properties that need to persist on the scene use `bpy.props.*` and are registered on `bpy.types.Scene` or `bpy.types.WindowManager`.
- Never block the main thread with long-running subprocess calls — use modal operators or `bpy.app.timers` if needed.

## Git / LFS Layer (`git_ops.py`)

This module has **no `bpy` imports** — it is pure Python calling `git` via `subprocess`. This makes it independently testable.

### Git dependency strategy: detect system git, fail gracefully

We use the system-installed `git` and `git-lfs` binaries. On startup (addon `register()`), call `check_dependencies()` which verifies both binaries are on PATH. If either is missing, set a flag that causes the panel to show a clear, plain-English error with install links instead of the normal UI. Never silently fail or crash.

```python
def check_dependencies() -> dict:
    """Returns {"git": bool, "git_lfs": bool}"""
```

Error message to show users when git is missing:

> "Git is not installed. Please install it from git-scm.com, then restart Blender."

Error message when git-lfs is missing:

> "Git LFS is not installed. Please install it from git-lfs.com, then restart Blender."

### Key operations needed

- `check_dependencies()` — verify `git` and `git-lfs` are on PATH
- `init_repo(path)` — `git init`, set default branch to `main`, write `.gitattributes` for LFS, run `git lfs install`
- `commit(repo_path, message)` — stage all (`git add -A`) and commit
- `create_branch(repo_path, name)` — `git checkout -b <name>`
- `checkout(repo_path, ref)` — commit any floating changes first, then `git checkout <ref>`
- `list_branches(repo_path)` — parse `git branch` output
- `get_log(repo_path)` — parse `git log` for timeline display
- `has_uncommitted_changes(repo_path)` — `git status --porcelain`
- `is_git_repo(path)` — `git rev-parse --git-dir`
- `get_current_branch(repo_path)` — `git branch --show-current`
- `sanitize_branch_name(name)` — pure string, no subprocess

**Critical constraint**: Never allow a checkout with uncommitted changes — binary files cannot be diffed/merged. Always auto-commit or block the action.

## State Scenarios

**No file open / no git repo**: Show only "Initialize" button.

**Initialized, on a branch**: Show commit button, branch switcher dropdown, create branch button, timeline panel.

**After any checkout**: Must force Blender to reopen the `.blend` file so LFS pointers resolve to the correct binary version. Use `bpy.ops.wm.open_mainfile(filepath=...)`.

## UI Guidelines

- Sidebar panel location: `VIEW_3D` > `UI` tab, category `"Git"`
- Current branch always visible at top of panel (or "Not initialized")
- Timeline panel: separate floating panel, left of main panel, full screen height, min 320px wide, scrollable
- Primary branch color defaults to `rgb(0, 208, 153)`, user-configurable in addon preferences
- Only show actions that are currently valid — never render a button for an impossible state
- Branch name input: sanitize spaces to `-`, validate against git branch name rules before allowing creation

## Development / Testing

Since `bpy` is only available inside Blender, test `git_ops.py` functions directly with Python outside Blender. For UI testing, install the addon in Blender via Edit > Preferences > Add-ons > Install.

To reload during development without restarting Blender, use the [Blender Development](https://marketplace.visualstudio.com/items?itemName=JacquesLucke.blender-development) VSCode extension for live reload, or in the Python console:

```python
bpy.ops.preferences.addon_disable(module="blender-git")
bpy.ops.preferences.addon_enable(module="blender-git")
```

## Key Design Principles

1. **Never float binary changes** — before any `git checkout`, always ensure the working tree is clean (commit or abort).
2. **Always reload after checkout** — LFS objects won't update until the `.blend` file is reopened.
3. **Minimal UI** — only show what's actionable in the current state.
4. **No git knowledge required** — error messages and labels must be plain English, not git terminology.
