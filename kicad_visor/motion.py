"""Turntable motions: which axis the board turns around, and which way."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

# The axes a board can turn around, as seen by the camera, and the ways it
# can go: which way the face toward the camera moves. The first direction
# is the default.
#   x: the horizontal screen axis, like a rolling drum: "down" or "up".
#   y: the vertical screen axis, like a revolving door: "right" or "left".
#   z: the board's own normal, like a record: "ccw" or "cw".
AXES: Dict[str, Tuple[str, str]] = {
    "x": ("down", "up"),
    "y": ("right", "left"),
    "z": ("ccw", "cw"),
}

# A "z" spin is seen from above at this angle; flat on, it would look like
# a picture rotating.
TILT = -55


def check(axis: str, direction: Optional[str] = None) -> str:
    """The direction to use for `axis`, after checking both; None is the default."""
    if axis not in AXES:
        raise ValueError(f"turntable axis must be one of {list(AXES)}, not {axis!r}")
    if direction is None:
        return AXES[axis][0]
    if direction not in AXES[axis]:
        raise ValueError(f"turntable direction around {axis!r} must be one of "
                         f"{list(AXES[axis])}, not {direction!r}")
    return direction


def rotation(axis: str, direction: str, t: float) -> Tuple[float, float, float]:
    """kicad-cli --rotate angles at `t` (0 to 1) of the way through the loop."""
    # Positive angles move the face toward the camera down (x), right (y)
    # and counterclockwise (z); kicad-cli applies z in the board's own frame
    # before the x tilt.
    sign = 1 if direction == AXES[axis][0] else -1
    angle = sign * 360 * t
    if axis == "x":
        return (angle, 0, 0)
    if axis == "y":
        return (0, angle, 0)
    return (TILT, 0, angle)
