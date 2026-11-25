from app.contexts.identity.infrastructure.login_throttle import LoginThrottle


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_blocks_after_max_failures_and_reopens_after_window():
    clock = Clock()
    t = LoginThrottle(max_per_account=3, max_per_ip=100, window_seconds=60, clock=clock)
    for _ in range(3):
        assert t.retry_after("A@x.dz", "1.1.1.1") is None
        t.record_failure("A@x.dz", "1.1.1.1")
        clock.now += 1
    assert t.retry_after(" a@x.dz ", "1.1.1.1") == 57  # normalised email; oldest failure at 1000, now 1003
    assert t.retry_after("a@x.dz", "2.2.2.2") is None  # other IP unaffected
    clock.now = 1000 + 60
    assert t.retry_after("a@x.dz", "1.1.1.1") is None  # oldest failure expired


def test_success_resets_account_but_not_ip_counter():
    t = LoginThrottle(max_per_account=2, max_per_ip=3, window_seconds=60, clock=Clock())
    t.record_failure("a@x.dz", "ip")
    t.record_failure("a@x.dz", "ip")
    assert t.retry_after("a@x.dz", "ip") is not None
    t.reset("a@x.dz", "ip")
    assert t.retry_after("a@x.dz", "ip") is None
    t.record_failure("b@x.dz", "ip")  # 3rd failure from this IP -> IP limit reached
    assert t.retry_after("c@x.dz", "ip") is not None
