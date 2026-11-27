"""Counts model calls and tokens, so the cost of each eval run can be logged."""
import threading

_lock = threading.Lock()
_totals = {"calls": 0, "input_tokens": 0, "output_tokens": 0}


def record(response):
    """Add one Bedrock converse response to the running totals."""
    usage = response.get("usage", {})
    with _lock:
        _totals["calls"] += 1
        _totals["input_tokens"] += usage.get("inputTokens", 0)
        _totals["output_tokens"] += usage.get("outputTokens", 0)


def snapshot():
    with _lock:
        return dict(_totals)
