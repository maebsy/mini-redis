"""테스트 공용 도구: 시간을 마음대로 움직일 수 있는 가짜 시계."""


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds

    # DEBUG SLEEP 이 실제로 기다리지 않고 시계만 움직이도록 sleep 대용으로도 쓴다.
    def sleep(self, seconds: float) -> None:
        self.advance(seconds)
