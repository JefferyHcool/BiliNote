def format_timestamp(seconds: float) -> str:
    """Return human-readable timestamp: mm:ss for < 1 h, h:mm:ss for >= 1 h."""
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
