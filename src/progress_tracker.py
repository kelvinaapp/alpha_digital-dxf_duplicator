class ProgressTracker:
    def __init__(self):
        self._progress = 0.0
        self._status = 'Waiting for upload...'
        self._complete = False

    def update(self, progress, status):
        self._progress = progress
        self._status = status
        self._complete = (progress >= 1.0)

    def reset(self):
        self._progress = 0.0
        self._status = 'Starting process...'
        self._complete = False

    @property
    def data(self):
        return {
            'progress': self._progress,
            'status': self._status,
            'complete': self._complete
        }

progress_tracker = ProgressTracker()
