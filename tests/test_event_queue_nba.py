from hdl_sim.core.events import EventQueue


def test_event_queue_runs_nba_flush_after_active_events() -> None:
    queue = EventQueue()
    observed: list[str] = []

    queue.set_nba_flush(lambda: observed.append("nba"))

    queue.schedule(0, lambda: observed.append("active"))
    queue.run()

    assert observed == ["active", "nba"]
