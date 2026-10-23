"""Every user-facing Telegram string lives here."""

from app.core.models import Task, TaskStatus

STATUS_LABELS = {
    TaskStatus.PENDING: "Pending",
    TaskStatus.IN_PROGRESS: "In Progress",
    TaskStatus.COMPLETED: "Completed",
}

START = (
    "👋 Hi! Send me a task as text or a voice message and I'll save it.\n\n"
    "/list — show your open tasks\n"
    "/done <number> — mark a task completed"
)
TEXT_TASK_CREATED = "✅ Task #{number} created: {title}"
VOICE_RECEIVED = "🎤 Got it, transcribing…"
VOICE_TASK_CREATED = "✅ Task #{number} created from voice: {title}"
VOICE_FAILED = (
    "❌ Couldn't transcribe that voice note ({reason}). Please try again or send it as text."
)
VOICE_TOO_LARGE = "❌ Voice note is too long (max {max_mb} MB). Please send a shorter one."
STATUS_CHANGED = "🔄 Task #{number} moved to {status}: {title}"
NO_OPEN_TASKS = "You have no open tasks."
LIST_HEADER = "📋 Your open tasks:\n"
LIST_LINE = "#{number} [{status}] {title}"
TASK_DONE = "✅ Task #{number} completed: {title}"
TASK_NOT_FOUND = "❌ Task #{number} not found."
USAGE_DONE = "Usage: /done <task number>"
UNKNOWN_COMMAND = "Unknown command. Send /start to see what I can do."
UNSUPPORTED_MESSAGE = "I can only turn text or voice messages into tasks."
TITLE_TOO_LONG = "❌ That's too long for a task title (max {max_chars} characters)."
SOMETHING_WENT_WRONG = "⚠️ Something went wrong on my side. Please try again."

FAILURE_REASONS = {
    "file_too_large": "file too large",
    "download_failed": "could not download the audio",
    "transcription_failed": "transcription failed",
    "transcription_empty": "no speech detected",
    "internal_error": "internal error",
}


def status_changed(task: Task) -> str:
    return STATUS_CHANGED.format(
        number=task.number, status=STATUS_LABELS[task.status], title=task.title
    )
