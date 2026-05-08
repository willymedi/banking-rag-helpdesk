from src.application.ports.feedback_repository import FeedbackEntry, FeedbackRepository


class RecordFeedback:
    def __init__(self, repo: FeedbackRepository) -> None:
        self._repo = repo

    async def execute(self, entry: FeedbackEntry) -> None:
        await self._repo.save(entry)
