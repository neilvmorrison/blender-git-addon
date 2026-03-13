import hashlib
import math
import os
import time
from datetime import datetime

import blf
import bpy
import gpu
from gpu_extras.batch import batch_for_shader

from .git_ops import git_ops

_CACHE_TTL: float = 2.0
_GRAPH_MAX_COUNT: int = 200
_TIMELINE_WIDTH: float = 320.0
_TIMELINE_PADDING: float = 16.0
_GIT_PANEL_TOP_OFFSET: float = 44.0
_TIMELINE_HEADER_HEIGHT: float = 44.0
_TIMELINE_ROW_HEIGHT: float = 34.0
_TIMELINE_LANE_GAP: float = 28.0
_TIMELINE_NODE_RADIUS: float = 7.0
_TIMELINE_BORDER_RADIUS: float = 10.0
_TIMELINE_BRANCH_WIDTH: float = 3.0
_FONT_ID: int = 0
_FALLBACK_BRANCH_COLORS: list[tuple[float, float, float]] = [
    (0.984, 0.549, 0.235),
    (0.396, 0.722, 1.0),
    (0.863, 0.384, 0.953),
    (0.973, 0.808, 0.278),
    (0.376, 0.922, 0.659),
    (0.945, 0.443, 0.443),
]

_cache: dict = {}
_cache_time: float = 0.0
_cache_repo: str = ""

_timeline_cache: dict = {}
_timeline_cache_time: float = 0.0
_timeline_cache_repo: str = ""

_timeline_draw_handler = None
_timeline_mouse: dict[str, float | int | None] = {
    "window": None,
    "area": None,
    "x": None,
    "y": None,
}
_timeline_drag: dict[str, bool | float | None] = {
    "active": False,
    "start_mouse_x": None,
    "start_mouse_y": None,
    "start_offset_x": None,
    "start_offset_y": None,
}


def _first_free_lane(active_lanes: list[dict | None]) -> int:
    for index, slot in enumerate(active_lanes):
        if slot is None:
            return index
    return len(active_lanes)


def _find_lane_for_hash(active_lanes: list[dict | None], commit_hash: str) -> int | None:
    for index, slot in enumerate(active_lanes):
        if slot and slot["hash"] == commit_hash:
            return index
    return None


def _is_primary_branch(branch_name: str | None) -> bool:
    return branch_name in {"main", "master"}


def _choose_branch_name(
    branch_refs: list[str],
    inherited_branch: str | None,
) -> str | None:
    if inherited_branch and inherited_branch in branch_refs:
        return inherited_branch
    for branch_name in branch_refs:
        if _is_primary_branch(branch_name):
            return branch_name
    if branch_refs:
        return branch_refs[0]
    return inherited_branch


def _build_timeline_layout(entries: list[dict]) -> dict:
    active_lanes: list[dict | None] = []
    commits: list[dict] = []
    max_lane = 0

    for entry in entries:
        matching_lanes = [
            index
            for index, slot in enumerate(active_lanes)
            if slot and slot["hash"] == entry["hash"]
        ]
        inherited_branch = None
        lane = None

        if matching_lanes:
            lane = matching_lanes[0]
            inherited_candidates = [
                active_lanes[index]["branch"]
                for index in matching_lanes
                if active_lanes[index] and active_lanes[index]["branch"]
            ]
            inherited_branch = inherited_candidates[0] if inherited_candidates else None
            for index in matching_lanes:
                active_lanes[index] = None
        else:
            lane = _first_free_lane(active_lanes)

        while lane >= len(active_lanes):
            active_lanes.append(None)

        branch_name = _choose_branch_name(entry["branch_refs"], inherited_branch)
        active_lanes[lane] = None

        if entry["parents"]:
            active_lanes[lane] = {
                "hash": entry["parents"][0],
                "branch": branch_name,
            }
            for branch_index, parent_hash in enumerate(entry["parents"][1:], start=1):
                target_lane = _find_lane_for_hash(active_lanes, parent_hash)
                if target_lane is None:
                    target_lane = _first_free_lane(active_lanes)
                while target_lane >= len(active_lanes):
                    active_lanes.append(None)
                target_branch = None
                if branch_index < len(entry["branch_refs"]):
                    target_branch = entry["branch_refs"][branch_index]
                active_lanes[target_lane] = {
                    "hash": parent_hash,
                    "branch": target_branch or branch_name,
                }

        commit = dict(entry)
        commit["lane"] = lane
        commit["branch_name"] = branch_name or f"lane-{lane}"
        commits.append(commit)
        max_lane = max(max_lane, lane)

        while active_lanes and active_lanes[-1] is None:
            active_lanes.pop()

    index_by_hash = {
        commit["hash"]: index for index, commit in enumerate(commits)
    }
    for commit in commits:
        commit["parent_links"] = []
        for parent_hash in commit["parents"]:
            parent_index = index_by_hash.get(parent_hash)
            if parent_index is None:
                continue
            parent_commit = commits[parent_index]
            commit["parent_links"].append(
                {
                    "hash": parent_hash,
                    "index": parent_index,
                    "lane": parent_commit["lane"],
                }
            )
            max_lane = max(max_lane, parent_commit["lane"])

    return {
        "commits": commits,
        "max_lane": max_lane,
    }


def _get_git_state(repo_path: str) -> dict:
    global _cache, _cache_time, _cache_repo

    now = time.monotonic()
    if _cache and _cache_repo == repo_path and (now - _cache_time) < _CACHE_TTL:
        return _cache

    is_repo = git_ops.is_git_repo(repo_path)
    if is_repo:
        current_branch = git_ops.get_current_branch(repo_path) or "detached HEAD"
        branches = git_ops.list_branches(repo_path)
    else:
        current_branch = ""
        branches = []

    _cache = {
        "is_repo": is_repo,
        "current_branch": current_branch,
        "branches": branches,
    }
    _cache_time = now
    _cache_repo = repo_path
    return _cache


def _get_timeline_state(repo_path: str) -> dict:
    global _timeline_cache, _timeline_cache_time, _timeline_cache_repo

    now = time.monotonic()
    if (
        _timeline_cache
        and _timeline_cache_repo == repo_path
        and (now - _timeline_cache_time) < _CACHE_TTL
    ):
        return _timeline_cache

    entries = git_ops.get_timeline(repo_path, max_count=_GRAPH_MAX_COUNT)
    _timeline_cache = _build_timeline_layout(entries)
    _timeline_cache_time = now
    _timeline_cache_repo = repo_path
    return _timeline_cache


def invalidate_cache() -> None:
    global _cache, _cache_time, _cache_repo
    global _timeline_cache, _timeline_cache_time, _timeline_cache_repo
    _cache = {}
    _cache_time = 0.0
    _cache_repo = ""
    _timeline_cache = {}
    _timeline_cache_time = 0.0
    _timeline_cache_repo = ""
    tag_view3d_redraw()


def is_repo_cached(repo_path: str) -> bool:
    return _get_git_state(repo_path).get("is_repo", False)


def _get_deps() -> dict[str, bool]:
    from . import _deps
    return _deps


def _is_git_panel_visible(area) -> bool:
    if not area or area.type != "VIEW_3D":
        return False
    for reg in area.regions:
        if reg.type == "UI":
            cat = getattr(reg, "active_panel_category", "UNSUPPORTED")
            if cat == "UNSUPPORTED":
                return True
            return cat == "Git"
    return False


def _get_overlay_bounds(region, wm) -> dict[str, float]:
    max_width = max(180.0, region.width - (_TIMELINE_PADDING * 2.0))
    width = min(max_width, max(_TIMELINE_WIDTH, region.width * 0.24))
    height = max(
        160.0,
        region.height - _TIMELINE_PADDING - _GIT_PANEL_TOP_OFFSET,
    )
    default_x = region.width - width - _TIMELINE_PADDING
    x = default_x + getattr(wm, "git_timeline_offset_x", 0.0)
    y = _TIMELINE_PADDING + getattr(wm, "git_timeline_offset_y", 0.0)
    return {
        "x": x,
        "y": y,
        "width": width,
        "height": height,
    }


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _extract_rgb(value) -> tuple[float, float, float] | None:
    try:
        channels = tuple(float(channel) for channel in value[:3])
    except (TypeError, ValueError, AttributeError, IndexError):
        try:
            channels = tuple(float(channel) for channel in list(value)[:3])
        except (TypeError, ValueError):
            return None
    if len(channels) < 3:
        return None
    return tuple(_clamp(channel, 0.0, 1.0) for channel in channels[:3])


def _unique_colors(colors: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    unique: list[tuple[float, float, float]] = []
    seen: set[tuple[float, float, float]] = set()
    for color in colors:
        key = tuple(round(channel, 3) for channel in color)
        if key in seen:
            continue
        unique.append(color)
        seen.add(key)
    return unique


def _get_theme_branch_colors(context) -> list[tuple[float, float, float]]:
    try:
        theme = context.preferences.themes[0]
    except (AttributeError, IndexError, TypeError):
        return _FALLBACK_BRANCH_COLORS

    candidates: list[tuple[float, float, float]] = []
    for theme_group_name, attr_names in (
        ("view_3d", ("vertex_select", "edge_select", "face_select")),
        ("user_interface", ("axis_x", "axis_y", "axis_z")),
    ):
        theme_group = getattr(theme, theme_group_name, None)
        if not theme_group:
            continue
        for attr_name in attr_names:
            color = _extract_rgb(getattr(theme_group, attr_name, None))
            if color:
                candidates.append(color)

    colors = _unique_colors(candidates)
    return colors or _FALLBACK_BRANCH_COLORS


def _get_main_branch_color(context) -> tuple[float, float, float]:
    addon = context.preferences.addons.get("blender-git")
    if not addon:
        return (0.0, 0.816, 0.6)
    return tuple(addon.preferences.main_branch_color)


def _get_branch_color(context, branch_name: str | None) -> tuple[float, float, float]:
    if _is_primary_branch(branch_name):
        return _get_main_branch_color(context)
    if not branch_name:
        return (0.62, 0.62, 0.62)

    palette = _get_theme_branch_colors(context)
    branch_hash = hashlib.sha1(branch_name.encode("utf-8")).hexdigest()
    index = int(branch_hash[:8], 16) % len(palette)
    return palette[index]


def _with_alpha(color: tuple[float, float, float], alpha: float) -> tuple[float, float, float, float]:
    return (color[0], color[1], color[2], alpha)


def _draw_batch(mode: str, coords: list[tuple[float, float]], color: tuple[float, ...]) -> None:
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batch = batch_for_shader(shader, mode, {"pos": coords})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


def _draw_polyline(
    points: list[tuple[float, float]],
    color: tuple[float, float, float, float],
    width: float,
) -> None:
    if len(points) < 2:
        return
    gpu.state.blend_set("ALPHA")
    gpu.state.line_width_set(width)
    _draw_batch("LINE_STRIP", points, color)
    gpu.state.line_width_set(1.0)
    gpu.state.blend_set("NONE")


def _draw_filled_circle(
    x: float,
    y: float,
    radius: float,
    color: tuple[float, float, float, float],
    segments: int = 24,
) -> None:
    points = [(x, y)]
    for index in range(segments + 1):
        angle = (math.tau * index) / segments
        points.append((x + math.cos(angle) * radius, y + math.sin(angle) * radius))
    gpu.state.blend_set("ALPHA")
    _draw_batch("TRI_FAN", points, color)
    gpu.state.blend_set("NONE")


def _draw_circle_outline(
    x: float,
    y: float,
    radius: float,
    color: tuple[float, float, float, float],
    width: float,
    segments: int = 28,
) -> None:
    points = []
    for index in range(segments + 1):
        angle = (math.tau * index) / segments
        points.append((x + math.cos(angle) * radius, y + math.sin(angle) * radius))
    _draw_polyline(points, color, width)


def _draw_rect(
    x: float,
    y: float,
    width: float,
    height: float,
    color: tuple[float, float, float, float],
) -> None:
    gpu.state.blend_set("ALPHA")
    _draw_batch(
        "TRI_FAN",
        [
            (x, y),
            (x + width, y),
            (x + width, y + height),
            (x, y + height),
        ],
        color,
    )
    gpu.state.blend_set("NONE")


def _draw_text(
    x: float,
    y: float,
    text: str,
    size: int,
    color: tuple[float, float, float, float],
) -> None:
    blf.position(_FONT_ID, x, y, 0)
    blf.size(_FONT_ID, size)
    blf.color(_FONT_ID, *color)
    blf.draw(_FONT_ID, text)


def _format_commit_time(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def _timeline_max_scroll(graph: dict, bounds: dict[str, float]) -> float:
    visible_height = max(0.0, bounds["height"] - _TIMELINE_HEADER_HEIGHT - 12.0)
    content_height = max(0.0, len(graph["commits"]) * _TIMELINE_ROW_HEIGHT)
    return max(0.0, content_height - visible_height)


def _timeline_view_offset(graph: dict, bounds: dict[str, float], wm) -> float:
    max_scroll = _timeline_max_scroll(graph, bounds)
    scroll = _clamp(wm.git_timeline_scroll, 0.0, max_scroll)
    if scroll != wm.git_timeline_scroll:
        wm.git_timeline_scroll = scroll
    if wm.git_timeline_order == "BOTTOM_UP":
        return max_scroll - scroll
    return scroll


def _display_row_index(total: int, logical_index: int, order: str) -> int:
    if order == "BOTTOM_UP":
        return (total - 1) - logical_index
    return logical_index


def _get_mouse_for_area(context) -> tuple[float | None, float | None]:
    area = getattr(context, "area", None)
    window = getattr(context, "window", None)
    if not area or not window:
        return (None, None)
    if _timeline_mouse["area"] != area.as_pointer():
        return (None, None)
    if _timeline_mouse["window"] != window.as_pointer():
        return (None, None)
    return (_timeline_mouse["x"], _timeline_mouse["y"])


def tag_view3d_redraw() -> None:
    window_manager = getattr(bpy.context, "window_manager", None)
    if not window_manager:
        return
    for window in window_manager.windows:
        screen = window.screen
        if not screen:
            continue
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def update_timeline_mouse(context, event) -> None:
    area = getattr(context, "area", None)
    window = getattr(context, "window", None)
    if not area or area.type != "VIEW_3D" or not window:
        clear_timeline_mouse()
        return
    _timeline_mouse["window"] = window.as_pointer()
    _timeline_mouse["area"] = area.as_pointer()
    _timeline_mouse["x"] = float(event.mouse_region_x)
    _timeline_mouse["y"] = float(event.mouse_region_y)


def clear_timeline_mouse() -> None:
    _timeline_mouse["window"] = None
    _timeline_mouse["area"] = None
    _timeline_mouse["x"] = None
    _timeline_mouse["y"] = None


def ensure_timeline_handler() -> None:
    global _timeline_draw_handler
    if _timeline_draw_handler is None:
        _timeline_draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            _draw_timeline_overlay,
            (),
            "WINDOW",
            "POST_PIXEL",
        )
    tag_view3d_redraw()


def remove_timeline_handler() -> None:
    global _timeline_draw_handler
    if _timeline_draw_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_timeline_draw_handler, "WINDOW")
        _timeline_draw_handler = None
    clear_timeline_mouse()
    _clear_timeline_drag()
    tag_view3d_redraw()


def _point_in_header(bounds: dict[str, float], mouse_x: float, mouse_y: float) -> bool:
    header_bottom = bounds["y"] + bounds["height"] - _TIMELINE_HEADER_HEIGHT
    return (
        bounds["x"] <= mouse_x <= bounds["x"] + bounds["width"]
        and header_bottom <= mouse_y <= bounds["y"] + bounds["height"]
    )


def _clear_timeline_drag() -> None:
    global _timeline_drag
    _timeline_drag["active"] = False
    _timeline_drag["start_mouse_x"] = None
    _timeline_drag["start_mouse_y"] = None
    _timeline_drag["start_offset_x"] = None
    _timeline_drag["start_offset_y"] = None


def handle_timeline_event(context, event) -> bool:
    area = getattr(context, "area", None)
    region = getattr(context, "region", None)
    if not area or area.type != "VIEW_3D" or not region or region.type != "WINDOW":
        return False
    if not _is_git_panel_visible(area):
        return False
    if not bpy.data.filepath:
        return False

    repo_path = os.path.dirname(bpy.data.filepath)
    if not is_repo_cached(repo_path):
        return False

    graph = _get_timeline_state(repo_path)
    if not graph["commits"]:
        return False

    wm = context.window_manager
    bounds = _get_overlay_bounds(region, wm)
    mouse_x = float(event.mouse_region_x)
    mouse_y = float(event.mouse_region_y)
    inside = (
        bounds["x"] <= mouse_x <= (bounds["x"] + bounds["width"])
        and bounds["y"] <= mouse_y <= (bounds["y"] + bounds["height"])
    )
    in_header = _point_in_header(bounds, mouse_x, mouse_y)

    if event.type == "LEFTMOUSE":
        if event.value == "PRESS" and in_header:
            _timeline_drag["active"] = True
            _timeline_drag["start_mouse_x"] = mouse_x
            _timeline_drag["start_mouse_y"] = mouse_y
            _timeline_drag["start_offset_x"] = wm.git_timeline_offset_x
            _timeline_drag["start_offset_y"] = wm.git_timeline_offset_y
            tag_view3d_redraw()
            return True
        if event.value == "RELEASE" and _timeline_drag["active"]:
            _clear_timeline_drag()
            tag_view3d_redraw()
            return True

    if _timeline_drag["active"] and event.type == "MOUSEMOVE":
        dx = mouse_x - _timeline_drag["start_mouse_x"]
        dy = mouse_y - _timeline_drag["start_mouse_y"]
        wm.git_timeline_offset_x = _timeline_drag["start_offset_x"] + dx
        wm.git_timeline_offset_y = _timeline_drag["start_offset_y"] + dy
        tag_view3d_redraw()
        return True

    if event.type == "MOUSEMOVE":
        update_timeline_mouse(context, event)
        tag_view3d_redraw()
        return inside

    if event.type not in {"WHEELUPMOUSE", "WHEELDOWNMOUSE"} or not inside:
        return False

    max_scroll = _timeline_max_scroll(graph, bounds)
    if max_scroll <= 0.0:
        return False

    step = _TIMELINE_ROW_HEIGHT * 2.0
    if event.type == "WHEELUPMOUSE":
        wm.git_timeline_scroll = _clamp(wm.git_timeline_scroll + step, 0.0, max_scroll)
    else:
        wm.git_timeline_scroll = _clamp(wm.git_timeline_scroll - step, 0.0, max_scroll)
    tag_view3d_redraw()
    return True


def _draw_timeline_overlay() -> None:
    context = bpy.context
    wm = getattr(context, "window_manager", None)
    area = getattr(context, "area", None)
    region = getattr(context, "region", None)
    if not wm or not area or area.type != "VIEW_3D":
        return
    if not region or region.type != "WINDOW":
        return
    if not wm.git_timeline_visible or not bpy.data.filepath:
        return
    if not _is_git_panel_visible(area):
        return

    repo_path = os.path.dirname(bpy.data.filepath)
    if not is_repo_cached(repo_path):
        return

    graph = _get_timeline_state(repo_path)
    bounds = _get_overlay_bounds(region, wm)
    _draw_rect(
        bounds["x"],
        bounds["y"],
        bounds["width"],
        bounds["height"],
        (0.08, 0.08, 0.08, 0.92),
    )
    _draw_rect(
        bounds["x"],
        bounds["y"] + bounds["height"] - _TIMELINE_HEADER_HEIGHT,
        bounds["width"],
        _TIMELINE_HEADER_HEIGHT,
        (0.11, 0.11, 0.11, 0.96),
    )
    _draw_text(
        bounds["x"] + 14.0,
        bounds["y"] + bounds["height"] - 28.0,
        "Git Timeline",
        14,
        (1.0, 1.0, 1.0, 1.0),
    )
    _draw_text(
        bounds["x"] + bounds["width"] - 126.0,
        bounds["y"] + bounds["height"] - 28.0,
        "Bottom-Up" if wm.git_timeline_order == "BOTTOM_UP" else "Top-Down",
        11,
        (0.76, 0.76, 0.76, 1.0),
    )

    if not graph["commits"]:
        _draw_text(
            bounds["x"] + 14.0,
            bounds["y"] + bounds["height"] - _TIMELINE_HEADER_HEIGHT - 24.0,
            "No commits yet.",
            12,
            (0.85, 0.85, 0.85, 1.0),
        )
        return

    total_commits = len(graph["commits"])
    content_top = bounds["y"] + bounds["height"] - _TIMELINE_HEADER_HEIGHT - 10.0
    view_offset = _timeline_view_offset(graph, bounds, wm)
    lane_origin_x = bounds["x"] + 26.0
    node_positions: dict[str, dict[str, float | tuple[float, float, float]]] = {}

    for logical_index, commit in enumerate(graph["commits"]):
        row_index = _display_row_index(total_commits, logical_index, wm.git_timeline_order)
        row_y = content_top - (row_index * _TIMELINE_ROW_HEIGHT) + view_offset
        if row_y < bounds["y"] - 40.0 or row_y > (bounds["y"] + bounds["height"] + 20.0):
            continue
        lane_x = lane_origin_x + (commit["lane"] * _TIMELINE_LANE_GAP)
        branch_color = _get_branch_color(context, commit["branch_name"])
        node_positions[commit["hash"]] = {
            "x": lane_x,
            "y": row_y,
            "color": branch_color,
        }

    for commit in graph["commits"]:
        current_position = node_positions.get(commit["hash"])
        if not current_position:
            continue
        for parent_link in commit["parent_links"]:
            parent_position = node_positions.get(parent_link["hash"])
            if not parent_position:
                continue
            start_x = float(current_position["x"])
            start_y = float(current_position["y"])
            end_x = float(parent_position["x"])
            end_y = float(parent_position["y"])
            mid_y = start_y + ((end_y - start_y) * 0.5)
            _draw_polyline(
                [
                    (start_x, start_y),
                    (start_x, mid_y),
                    (end_x, mid_y),
                    (end_x, end_y),
                ],
                _with_alpha(current_position["color"], 0.92),
                _TIMELINE_BRANCH_WIDTH,
            )

    mouse_x, mouse_y = _get_mouse_for_area(context)
    hovered_commit = None

    for logical_index, commit in enumerate(graph["commits"]):
        position = node_positions.get(commit["hash"])
        if not position:
            continue
        center_x = float(position["x"])
        center_y = float(position["y"])
        branch_color = position["color"]
        _draw_filled_circle(
            center_x,
            center_y,
            _TIMELINE_NODE_RADIUS,
            (1.0, 1.0, 1.0, 1.0),
        )
        _draw_circle_outline(
            center_x,
            center_y,
            _TIMELINE_BORDER_RADIUS,
            _with_alpha(branch_color, 1.0),
            4.0,
        )

        label_x = lane_origin_x + ((graph["max_lane"] + 1) * _TIMELINE_LANE_GAP) + 16.0
        label = f"{commit['short_hash']}  {commit['message']}"
        max_chars = max(20, int((bounds["width"] - (label_x - bounds["x"]) - 12.0) / 7.0))
        if len(label) > max_chars:
            label = label[: max_chars - 1].rstrip() + "…"
        _draw_text(
            label_x,
            center_y - 5.0,
            label,
            11,
            (0.9, 0.9, 0.9, 1.0),
        )

        if mouse_x is not None and mouse_y is not None:
            if math.hypot(mouse_x - center_x, mouse_y - center_y) <= (_TIMELINE_BORDER_RADIUS + 4.0):
                hovered_commit = commit

    wm.git_timeline_hover_hash = hovered_commit["hash"] if hovered_commit else ""

    if hovered_commit and hovered_commit["hash"] in node_positions:
        position = node_positions[hovered_commit["hash"]]
        tooltip_x = min(
            float(position["x"]) + 18.0,
            bounds["x"] + bounds["width"] - 220.0,
        )
        tooltip_y = min(
            float(position["y"]) + 18.0,
            bounds["y"] + bounds["height"] - 84.0,
        )
        _draw_rect(tooltip_x, tooltip_y, 210.0, 70.0, (0.04, 0.04, 0.04, 0.97))
        _draw_text(
            tooltip_x + 10.0,
            tooltip_y + 46.0,
            hovered_commit["message"],
            12,
            (1.0, 1.0, 1.0, 1.0),
        )
        refs_text = ", ".join(hovered_commit["refs"]) if hovered_commit["refs"] else "No refs"
        _draw_text(
            tooltip_x + 10.0,
            tooltip_y + 28.0,
            f"{hovered_commit['short_hash']}  {refs_text}",
            10,
            (0.78, 0.78, 0.78, 1.0),
        )
        _draw_text(
            tooltip_x + 10.0,
            tooltip_y + 12.0,
            _format_commit_time(hovered_commit["timestamp"]),
            10,
            (0.66, 0.66, 0.66, 1.0),
        )


class GIT_PT_main(bpy.types.Panel):
    bl_label = "Git"
    bl_idname = "GIT_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Git"

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

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

        prefs = context.preferences.addons.get("blender-git")
        projects_dir = prefs.preferences.projects_dir if prefs else ""
        if not projects_dir:
            layout.label(text="Set a Projects Directory:", icon="INFO")
            layout.operator(
                "git.open_preferences",
                text="Open Preferences",
                icon="PREFERENCES",
            )
            return

        if not bpy.data.filepath:
            layout.operator("git.init_repo", icon="ADD")
            return

        repo_path = os.path.dirname(bpy.data.filepath)
        state = _get_git_state(repo_path)
        if not state["is_repo"]:
            layout.operator("git.init_repo", icon="ADD")
            return

        if wm.git_active_branch != state["current_branch"]:
            wm.git_active_branch = state["current_branch"]

        layout.separator()
        layout.prop(wm, "git_active_branch", text="Branch")
        row = layout.row()
        row.operator(
            "git.toggle_branch_input",
            text="New Branch" if not wm.git_show_branch_input else "Cancel",
            icon="PLUS",
        )
        if wm.git_show_branch_input:
            layout.prop(wm, "git_branch_name", text="")
            layout.operator(
                "git.create_branch",
                text="Create Branch",
                icon="CHECKMARK",
            )

        layout.separator()
        row = layout.row()
        row.operator(
            "git.toggle_commit_input",
            text="Create Commit" if not wm.git_show_commit_input else "Cancel",
            icon="FILE_TICK",
        )
        if wm.git_show_commit_input:
            layout.prop(wm, "git_commit_message", text="")
            layout.operator("git.commit", text="Commit", icon="CHECKMARK")

        layout.separator()
        timeline_box = layout.box()
        timeline_box.label(text="Timeline")
        row = timeline_box.row(align=True)
        row.operator(
            "git.toggle_timeline",
            text="Hide Timeline" if wm.git_timeline_visible else "Show Timeline",
            icon="HIDE_OFF" if wm.git_timeline_visible else "GRAPH",
        )
        row.operator(
            "git.cycle_timeline_order",
            text="Bottom-Up" if wm.git_timeline_order == "BOTTOM_UP" else "Top-Down",
            icon="SORTTIME",
        )
        row.operator("git.reset_timeline_position", text="", icon="LOOP_BACK")
        if wm.git_timeline_visible:
            timeline_box.label(text="Drag header to move. Scroll to browse.")


classes = [GIT_PT_main]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    remove_timeline_handler()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
