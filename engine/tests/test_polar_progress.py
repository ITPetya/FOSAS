from fosas_engine.polar_progress import aggregate_status


def test_all_pending_is_pending():
    assert aggregate_status(["pending", "pending"]) == "pending"


def test_all_done_is_done():
    assert aggregate_status(["done", "done"]) == "done"


def test_any_failed_among_terminal_is_failed():
    assert aggregate_status(["done", "failed"]) == "failed"
    assert aggregate_status(["failed", "failed"]) == "failed"


def test_mixed_pending_and_running_is_running():
    assert aggregate_status(["pending", "running"]) == "running"


def test_mixed_done_and_pending_is_running():
    # Not all done yet, not a failure either: still in progress overall.
    assert aggregate_status(["done", "pending"]) == "running"


def test_mixed_done_and_running_is_running():
    assert aggregate_status(["done", "running"]) == "running"
