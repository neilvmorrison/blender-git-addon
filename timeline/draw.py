from __future__ import annotations

import hashlib
import math
from datetime import datetime

import blf
import bpy
import gpu
from gpu_extras.batch import batch_for_shader

from ..lib import constants
from ..lib.timeline_graph import is_primary_branch


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _extract_rgb(value: object) -> tuple[float, float, float] | None:
    try:
        ch = tuple(float(c) for c in value[:3])
    except (TypeError, ValueError, AttributeError, IndexError):
        try:
            ch = tuple(float(c) for c in list(value)[:3])
        except (TypeError, ValueError):
            return None
    if len(ch) < 3:
        return None
    return tuple(clamp(c, 0.0, 1.0) for c in ch[:3])


def _unique_colors(colors: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    seen: set[tuple[float, float, float]] = set()
    out: list[tuple[float, float, float]] = []
    for c in colors:
        k = tuple(round(x, 3) for x in c)
        if k in seen:
            continue
        seen.add(k)
        out.append(c)
    return out


def get_theme_branch_colors(context: object) -> list[tuple[float, float, float]]:
    try:
        theme = context.preferences.themes[0]
    except (AttributeError, IndexError, TypeError):
        return constants.FALLBACK_BRANCH_COLORS

    candidates: list[tuple[float, float, float]] = []
    for group_name, attrs in (
        ("view_3d", ("vertex_select", "edge_select", "face_select")),
        ("user_interface", ("axis_x", "axis_y", "axis_z")),
    ):
        group = getattr(theme, group_name, None)
        if not group:
            continue
        for attr in attrs:
            c = _extract_rgb(getattr(group, attr, None))
            if c:
                candidates.append(c)

    out = _unique_colors(candidates)
    return out or constants.FALLBACK_BRANCH_COLORS


def get_main_branch_color(context: object) -> tuple[float, float, float]:
    addon = context.preferences.addons.get("blender-git")
    if not addon:
        return (0.0, 0.816, 0.6)
    return tuple(addon.preferences.main_branch_color)


def get_branch_color(context: object, branch_name: str | None) -> tuple[float, float, float]:
    if is_primary_branch(branch_name):
        return get_main_branch_color(context)
    if not branch_name:
        return (0.62, 0.62, 0.62)
    palette = get_theme_branch_colors(context)
    idx = int(hashlib.sha1(branch_name.encode()).hexdigest()[:8], 16) % len(palette)
    return palette[idx]


def with_alpha(color: tuple[float, float, float], alpha: float) -> tuple[float, float, float, float]:
    return (color[0], color[1], color[2], alpha)


def draw_batch(mode: str, coords: list[tuple[float, float]], color: tuple[float, ...]) -> None:
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batch = batch_for_shader(shader, mode, {"pos": coords})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


def draw_polyline(
    points: list[tuple[float, float]],
    color: tuple[float, float, float, float],
    width: float,
) -> None:
    if len(points) < 2:
        return
    gpu.state.blend_set("ALPHA")
    gpu.state.line_width_set(width)
    draw_batch("LINE_STRIP", points, color)
    gpu.state.line_width_set(1.0)
    gpu.state.blend_set("NONE")


def draw_filled_circle(
    x: float, y: float, radius: float,
    color: tuple[float, float, float, float],
    segments: int = 24,
) -> None:
    pts = [(x, y)]
    for i in range(segments + 1):
        a = math.tau * i / segments
        pts.append((x + math.cos(a) * radius, y + math.sin(a) * radius))
    gpu.state.blend_set("ALPHA")
    draw_batch("TRI_FAN", pts, color)
    gpu.state.blend_set("NONE")


def draw_circle_outline(
    x: float, y: float, radius: float,
    color: tuple[float, float, float, float],
    width: float,
    segments: int = 28,
) -> None:
    pts = [
        (x + math.cos(math.tau * i / segments) * radius, y + math.sin(math.tau * i / segments) * radius)
        for i in range(segments + 1)
    ]
    draw_polyline(pts, color, width)


def draw_rect(
    x: float, y: float, w: float, h: float,
    color: tuple[float, float, float, float],
) -> None:
    gpu.state.blend_set("ALPHA")
    draw_batch("TRI_FAN", [(x, y), (x + w, y), (x + w, y + h), (x, y + h)], color)
    gpu.state.blend_set("NONE")


def draw_text(
    x: float, y: float, text: str,
    size: int,
    color: tuple[float, float, float, float],
) -> None:
    blf.position(constants.FONT_ID, x, y, 0)
    blf.size(constants.FONT_ID, size)
    blf.color(constants.FONT_ID, *color)
    blf.draw(constants.FONT_ID, text)


def format_commit_time(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
