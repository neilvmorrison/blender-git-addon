from __future__ import annotations

import math
import os

import bpy

from ..lib import constants
from ..lib import git_cache
from ..lib import redraw
from . import draw

_timeline_draw_handler = None
_timeline_mouse: dict[str, float | int | None] = {
    "window": None, "area": None, "x": None, "y": None,
}
_timeline_drag: dict[str, bool | float | None] = {
    "active": False,
    "start_mouse_x": None,
    "start_mouse_y": None,
    "start_offset_x": None,
    "start_offset_y": None,
}


def is_git_panel_visible(area: object) -> bool:
    if not area or getattr(area, "type", None) != "VIEW_3D":
        return False
    for reg in getattr(area, "regions", []):
        if getattr(reg, "type", None) == "UI":
            cat = getattr(reg, "active_panel_category", "UNSUPPORTED")
            if cat == "UNSUPPORTED":
                return True
            return cat == "Git"
    return False


def get_overlay_bounds(region: object, wm: object) -> dict[str, float]:
    rw = getattr(region, "width", 0) or 1
    rh = getattr(region, "height", 0) or 1
    max_w = max(180.0, rw - constants.TIMELINE_PADDING * 2)
    width = min(max_w, max(constants.TIMELINE_WIDTH, rw * 0.24))
    height = max(
        160.0,
        rh - constants.TIMELINE_PADDING - constants.GIT_PANEL_TOP_OFFSET,
    )
    default_x = rw - width - constants.TIMELINE_PADDING
    ox = getattr(wm, "git_timeline_offset_x", 0.0) or 0.0
    oy = getattr(wm, "git_timeline_offset_y", 0.0) or 0.0
    return {
        "x": default_x + ox,
        "y": constants.TIMELINE_PADDING + oy,
        "width": width,
        "height": height,
    }


def timeline_max_scroll(graph: dict, bounds: dict[str, float]) -> float:
    vis = max(0.0, bounds["height"] - constants.TIMELINE_HEADER_HEIGHT - 12.0)
    content = max(0.0, len(graph["commits"]) * constants.TIMELINE_ROW_HEIGHT)
    return max(0.0, content - vis)


def timeline_view_offset(graph: dict, bounds: dict[str, float], wm: object) -> float:
    max_scroll = timeline_max_scroll(graph, bounds)
    scroll = draw.clamp(
        getattr(wm, "git_timeline_scroll", 0.0) or 0.0,
        0.0, max_scroll,
    )
    if scroll != getattr(wm, "git_timeline_scroll", 0.0):
        wm.git_timeline_scroll = scroll
    order = getattr(wm, "git_timeline_order", "BOTTOM_UP") or "BOTTOM_UP"
    return max_scroll - scroll if order == "BOTTOM_UP" else scroll


def display_row_index(total: int, logical: int, order: str) -> int:
    return (total - 1) - logical if order == "BOTTOM_UP" else logical


def get_mouse_for_area(context: object) -> tuple[float | None, float | None]:
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
    redraw.tag_view3d_redraw()


def update_timeline_mouse(context: object, event: object) -> None:
    area = getattr(context, "area", None)
    window = getattr(context, "window", None)
    if not area or getattr(area, "type", None) != "VIEW_3D" or not window:
        clear_timeline_mouse()
        return
    _timeline_mouse["window"] = window.as_pointer()
    _timeline_mouse["area"] = area.as_pointer()
    _timeline_mouse["x"] = float(getattr(event, "mouse_region_x", 0))
    _timeline_mouse["y"] = float(getattr(event, "mouse_region_y", 0))


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


def _point_in_header(bounds: dict[str, float], mx: float, my: float) -> bool:
    hb = bounds["y"] + bounds["height"] - constants.TIMELINE_HEADER_HEIGHT
    return (
        bounds["x"] <= mx <= bounds["x"] + bounds["width"]
        and hb <= my <= bounds["y"] + bounds["height"]
    )


def _clear_timeline_drag() -> None:
    global _timeline_drag
    _timeline_drag["active"] = False
    _timeline_drag["start_mouse_x"] = None
    _timeline_drag["start_mouse_y"] = None
    _timeline_drag["start_offset_x"] = None
    _timeline_drag["start_offset_y"] = None


def handle_timeline_event(context: object, event: object) -> bool:
    area = getattr(context, "area", None)
    region = getattr(context, "region", None)
    if not area or getattr(area, "type", None) != "VIEW_3D":
        return False
    if not region or getattr(region, "type", None) != "WINDOW":
        return False
    if not is_git_panel_visible(area):
        return False
    if not bpy.data.filepath:
        return False

    repo_path = os.path.dirname(bpy.data.filepath)
    if not git_cache.is_repo_cached(repo_path):
        return False

    graph = git_cache.get_timeline_state(repo_path)
    if not graph["commits"]:
        return False

    wm = context.window_manager
    bounds = get_overlay_bounds(region, wm)
    mx = float(getattr(event, "mouse_region_x", 0))
    my = float(getattr(event, "mouse_region_y", 0))
    inside = (
        bounds["x"] <= mx <= bounds["x"] + bounds["width"]
        and bounds["y"] <= my <= bounds["y"] + bounds["height"]
    )
    in_header = _point_in_header(bounds, mx, my)

    if getattr(event, "type", "") == "LEFTMOUSE":
        if getattr(event, "value", "") == "PRESS" and in_header:
            _timeline_drag["active"] = True
            _timeline_drag["start_mouse_x"] = mx
            _timeline_drag["start_mouse_y"] = my
            _timeline_drag["start_offset_x"] = wm.git_timeline_offset_x
            _timeline_drag["start_offset_y"] = wm.git_timeline_offset_y
            tag_view3d_redraw()
            return True
        if getattr(event, "value", "") == "RELEASE" and _timeline_drag["active"]:
            _clear_timeline_drag()
            tag_view3d_redraw()
            return True

    if _timeline_drag["active"] and getattr(event, "type", "") == "MOUSEMOVE":
        dx = mx - (_timeline_drag["start_mouse_x"] or 0)
        dy = my - (_timeline_drag["start_mouse_y"] or 0)
        wm.git_timeline_offset_x = (_timeline_drag["start_offset_x"] or 0) + dx
        wm.git_timeline_offset_y = (_timeline_drag["start_offset_y"] or 0) + dy
        tag_view3d_redraw()
        return True

    if getattr(event, "type", "") == "MOUSEMOVE":
        update_timeline_mouse(context, event)
        tag_view3d_redraw()
        return inside

    if getattr(event, "type", "") not in {"WHEELUPMOUSE", "WHEELDOWNMOUSE"} or not inside:
        return False

    max_scroll = timeline_max_scroll(graph, bounds)
    if max_scroll <= 0.0:
        return False

    step = constants.TIMELINE_ROW_HEIGHT * 2.0
    if getattr(event, "type", "") == "WHEELUPMOUSE":
        wm.git_timeline_scroll = draw.clamp(
            wm.git_timeline_scroll + step, 0.0, max_scroll,
        )
    else:
        wm.git_timeline_scroll = draw.clamp(
            wm.git_timeline_scroll - step, 0.0, max_scroll,
        )
    tag_view3d_redraw()
    return True


def _draw_timeline_overlay() -> None:
    context = bpy.context
    wm = getattr(context, "window_manager", None)
    area = getattr(context, "area", None)
    region = getattr(context, "region", None)
    if not wm or not area or getattr(area, "type", None) != "VIEW_3D":
        return
    if not region or getattr(region, "type", None) != "WINDOW":
        return
    if not getattr(wm, "git_timeline_visible", False) or not bpy.data.filepath:
        return
    if not is_git_panel_visible(area):
        return

    repo_path = os.path.dirname(bpy.data.filepath)
    if not git_cache.is_repo_cached(repo_path):
        return

    graph = git_cache.get_timeline_state(repo_path)
    bounds = get_overlay_bounds(region, wm)
    draw.draw_rect(
        bounds["x"], bounds["y"], bounds["width"], bounds["height"],
        (0.08, 0.08, 0.08, 0.92),
    )
    draw.draw_rect(
        bounds["x"],
        bounds["y"] + bounds["height"] - constants.TIMELINE_HEADER_HEIGHT,
        bounds["width"], constants.TIMELINE_HEADER_HEIGHT,
        (0.11, 0.11, 0.11, 0.96),
    )
    draw.draw_text(
        bounds["x"] + 14.0, bounds["y"] + bounds["height"] - 28.0,
        "Git Timeline", 28, (1.0, 1.0, 1.0, 1.0),
    )
    order = "Bottom-Up" if wm.git_timeline_order == "BOTTOM_UP" else "Top-Down"
    draw.draw_text(
        bounds["x"] + bounds["width"] - 220.0, bounds["y"] + bounds["height"] - 28.0,
        order, 22, (0.76, 0.76, 0.76, 1.0),
    )

    if not graph["commits"]:
        draw.draw_text(
            bounds["x"] + 14.0,
            bounds["y"] + bounds["height"] - constants.TIMELINE_HEADER_HEIGHT - 24.0,
            "No commits yet.", 24, (0.85, 0.85, 0.85, 1.0),
        )
        return

    total = len(graph["commits"])
    content_top = bounds["y"] + bounds["height"] - constants.TIMELINE_HEADER_HEIGHT - 10.0
    view_offset = timeline_view_offset(graph, bounds, wm)
    lane_origin_x = bounds["x"] + 26.0
    node_positions: dict[str, dict] = {}

    for li, commit in enumerate(graph["commits"]):
        ri = display_row_index(total, li, wm.git_timeline_order)
        row_y = content_top - (ri * constants.TIMELINE_ROW_HEIGHT) + view_offset
        if row_y < bounds["y"] - 40.0 or row_y > bounds["y"] + bounds["height"] + 20.0:
            continue
        lane_x = lane_origin_x + (commit["lane"] * constants.TIMELINE_LANE_GAP)
        branch_color = draw.get_branch_color(context, commit["branch_name"])
        node_positions[commit["hash"]] = {"x": lane_x, "y": row_y, "color": branch_color}

    for commit in graph["commits"]:
        pos = node_positions.get(commit["hash"])
        if not pos:
            continue
        for pl in commit["parent_links"]:
            pp = node_positions.get(pl["hash"])
            if not pp:
                continue
            sx, sy = float(pos["x"]), float(pos["y"])
            ex, ey = float(pp["x"]), float(pp["y"])
            mid_y = sy + (ey - sy) * 0.5
            draw.draw_polyline(
                [(sx, sy), (sx, mid_y), (ex, mid_y), (ex, ey)],
                draw.with_alpha(pos["color"], 0.92),
                constants.TIMELINE_BRANCH_WIDTH,
            )

    for db in graph["dangling_branches"]:
        ap = node_positions.get(db["anchor_hash"])
        if not ap:
            continue
        bc = draw.get_branch_color(context, db["branch_name"])
        sx, sy = float(ap["x"]), float(ap["y"])
        ex = lane_origin_x + db["lane"] * constants.TIMELINE_LANE_GAP
        dy = constants.TIMELINE_ROW_HEIGHT * (0.65 if wm.git_timeline_order == "TOP_DOWN" else -0.65)
        mid_y = sy + dy * 0.5
        draw.draw_polyline(
            [(sx, sy), (sx, mid_y), (ex, mid_y), (ex, sy + dy)],
            draw.with_alpha(bc, 0.92),
            constants.TIMELINE_BRANCH_WIDTH,
        )

    mouse_x, mouse_y = get_mouse_for_area(context)
    hovered_commit = None

    for commit in graph["commits"]:
        pos = node_positions.get(commit["hash"])
        if not pos:
            continue
        cx, cy = float(pos["x"]), float(pos["y"])
        draw.draw_filled_circle(
            cx, cy, constants.TIMELINE_NODE_RADIUS,
            (1.0, 1.0, 1.0, 1.0),
        )
        draw.draw_circle_outline(
            cx, cy, constants.TIMELINE_BORDER_RADIUS,
            draw.with_alpha(pos["color"], 1.0),
            constants.TIMELINE_CIRCLE_OUTLINE_WIDTH,
        )
        label_x = lane_origin_x + (graph["max_lane"] + 1) * constants.TIMELINE_LANE_GAP + 16.0
        label = f"{commit['short_hash']}  {commit['message']}"
        max_chars = max(20, int((bounds["width"] - (label_x - bounds["x"]) - 12.0) / 14.0))
        if len(label) > max_chars:
            label = label[: max_chars - 1].rstrip() + "…"
        draw.draw_text(label_x, cy - 5.0, label, 22, (0.9, 0.9, 0.9, 1.0))

        if mouse_x is not None and mouse_y is not None:
            if math.hypot(mouse_x - cx, mouse_y - cy) <= constants.TIMELINE_BORDER_RADIUS + 4.0:
                hovered_commit = commit

    wm.git_timeline_hover_hash = hovered_commit["hash"] if hovered_commit else ""

    if hovered_commit and hovered_commit["hash"] in node_positions:
        pos = node_positions[hovered_commit["hash"]]
        tx = min(float(pos["x"]) + 18.0, bounds["x"] + bounds["width"] - 340.0)
        ty = min(float(pos["y"]) + 18.0, bounds["y"] + bounds["height"] - 104.0)
        draw.draw_rect(tx, ty, 320.0, 100.0, (0.04, 0.04, 0.04, 0.97))
        draw.draw_text(tx + 10.0, ty + 70.0, hovered_commit["message"], 24, (1.0, 1.0, 1.0, 1.0))
        refs_text = ", ".join(hovered_commit["refs"]) if hovered_commit.get("refs") else "No refs"
        draw.draw_text(tx + 10.0, ty + 42.0, f"{hovered_commit['short_hash']}  {refs_text}", 20, (0.78, 0.78, 0.78, 1.0))
        draw.draw_text(tx + 10.0, ty + 16.0, draw.format_commit_time(hovered_commit["timestamp"]), 20, (0.66, 0.66, 0.66, 1.0))
