from app.ratelimit import RateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_allows_up_to_limit_then_blocks():
    limiter = RateLimiter(limit=2, window_seconds=60, clock=FakeClock())
    assert limiter.check("1.2.3.4") is None
    assert limiter.check("1.2.3.4") is None
    assert limiter.check("1.2.3.4") == 60


def test_clients_are_limited_independently():
    limiter = RateLimiter(limit=1, clock=FakeClock())
    assert limiter.check("a") is None
    assert limiter.check("b") is None
    assert limiter.check("a") is not None


def test_window_slides():
    clock = FakeClock()
    limiter = RateLimiter(limit=1, window_seconds=60, clock=clock)
    assert limiter.check("a") is None
    clock.now += 45
    assert limiter.check("a") == 15
    clock.now += 15
    assert limiter.check("a") is None
