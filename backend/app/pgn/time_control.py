from __future__ import annotations


def classify_time_control(time_control: str | None) -> str | None:
    if not time_control or time_control in {"?", "-"}:
        return None

    value = time_control.strip()
    if "/" in value:
        return "Daily / Correspondence"

    first = value.split(":", 1)[0]
    base_text, _, increment_text = first.partition("+")
    try:
        base_seconds = int(base_text)
        increment_seconds = int(increment_text) if increment_text else 0
    except ValueError:
        return None

    estimated_seconds = base_seconds + increment_seconds * 40
    if base_seconds >= 86_400:
        return "Daily / Correspondence"
    if estimated_seconds < 180:
        return "Bullet"
    if estimated_seconds < 600:
        return "Blitz"
    if estimated_seconds < 3600:
        return "Rapid"
    return "Classical"
