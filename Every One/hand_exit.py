class ThumbsUpExit:
    def __init__(self, hold_time_ms=1000):
        self.hold_time_ms = hold_time_ms
        self.started_at = None

    def update(self, is_detected, gesture, current_time):
        if not is_detected or gesture != "Thumbs Up":
            self.started_at = None
            return False

        if self.started_at is None:
            self.started_at = current_time

        return current_time - self.started_at >= self.hold_time_ms
