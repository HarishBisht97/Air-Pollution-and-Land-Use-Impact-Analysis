from __future__ import annotations

import math


def inverse_distance_weight(
    x: float,
    y: float,
    stations: list[tuple[float, float, float]],
    power: float = 2.0,
    min_distance_m: float = 1.0,
) -> float | None:
    """IDW in projected metres. `stations` are (x, y, value)."""
    if not stations:
        return None
    weighted_sum = 0.0
    weight_total = 0.0
    for sx, sy, value in stations:
        dist = math.hypot(x - sx, y - sy)
        if dist < min_distance_m:
            return float(value)
        w = 1.0 / (dist**power)
        weighted_sum += w * value
        weight_total += w
    if weight_total == 0:
        return None
    return weighted_sum / weight_total
