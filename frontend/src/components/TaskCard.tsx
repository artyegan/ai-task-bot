import { useDraggable } from "@dnd-kit/core";
import { STATUSES, STATUS_LABEL, displayName, timeAgo, type Task, type TaskStatus } from "../lib/api";

interface Props {
  task: Task;
  onStatus: (status: TaskStatus) => void;
  onDelete: () => void;
  highlight?: boolean;
}

export function TaskCard({ task, onStatus, onDelete, highlight }: Props) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: task.id,
    data: { status: task.status },
  });
  const style = transform
    ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` }
    : undefined;

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`rounded-lg border bg-white p-3 shadow-sm transition-shadow ${
        isDragging ? "z-10 shadow-xl opacity-90" : ""
      } ${highlight ? "ring-2 ring-emerald-400" : "border-slate-200"}`}
    >
      <div
        {...listeners}
        {...attributes}
        className="cursor-grab touch-none select-none active:cursor-grabbing"
      >
        <div className="flex items-start justify-between gap-2">
          <p className="break-words text-sm font-medium leading-snug">{task.title}</p>
          {task.source === "voice" && (
            <span title="Created from a voice message" className="shrink-0 text-base" aria-label="voice">
              🎤
            </span>
          )}
        </div>
        <p className="mt-1 text-xs text-slate-500">
          #{task.number} · {displayName(task.user)} · {timeAgo(task.created_at)}
        </p>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1">
        {STATUSES.filter((s) => s !== task.status).map((s) => (
          <button
            key={s}
            onClick={() => onStatus(s)}
            className="rounded border border-slate-300 px-2 py-0.5 text-xs hover:bg-slate-100"
          >
            → {STATUS_LABEL[s]}
          </button>
        ))}
        <button
          onClick={onDelete}
          className="ml-auto rounded px-2 py-0.5 text-xs text-slate-400 hover:bg-red-50 hover:text-red-600"
          aria-label={`Delete task ${task.number}`}
        >
          ✕
        </button>
      </div>
    </div>
  );
}
