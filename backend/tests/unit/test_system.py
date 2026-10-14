from datetime import UTC

from app.infrastructure.system import SystemClock, UuidGenerator


def test_clock_returns_aware_utc_time() -> None:
    now = SystemClock().now()

    assert now.tzinfo is UTC


def test_id_generator_returns_unique_ids() -> None:
    ids = UuidGenerator()

    assert ids.new_id() != ids.new_id()
