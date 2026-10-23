"""Domain errors. The API maps these to the error envelope in PLAN 4b."""


class NotFoundError(Exception):
    code = "not_found"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class TaskNotFound(NotFoundError):
    code = "task_not_found"

    def __init__(self, task_id: int) -> None:
        super().__init__(f"Task {task_id} does not exist")


class UserNotFound(NotFoundError):
    code = "user_not_found"

    def __init__(self, user_id: int) -> None:
        super().__init__(f"User {user_id} does not exist")
