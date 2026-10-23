import { useDroppable } from "@dnd-kit/core";
import { STATUS_LABEL, type Task, type TaskStatus } from "../lib/api";
import { TaskCard } from "./TaskCard";

const ACCENT: Record<TaskStatus, string> = {
  pending: "border-t-amber-400",
  in_progress: "border-t-sky-500",
  completed: "border-t-emerald-500",
};

interface Props {
  status: TaskStatus;
  tasks: Task[];
  highlightId: number | null;
  onStatus: (id: number, status: TaskStatus) => void;
  onDelete: (id: number) => void;
}

export function Column({ status, tasks, highlightId, onStatus, onDelete }: Props) {
  const { setNodeRef, isOver } = useDroppable({ id: status });
  return (
    <section
      ref={setNodeRef}
      className={`flex min-h-[12rem] flex-col rounded-xl border-t-4 bg-slate-50 p-3 ${ACCENT[status]} ${
        isOver ? "bg-slate-200" : ""
      }`}
    >
      <h2 className="mb-3 flex items-center justify-between text-sm font-semibold uppercase tracking-wide text-slate-600">
        {STATUS_LABEL[status]}
        <span className="rounded-full bg-white px-2 py-0.5 text-xs font-normal text-slate-500">
          {tasks.length}
        </span>
      </h2>
      <div className="flex flex-col gap-2">
        {tasks.map((t) => (
          <TaskCard
            key={t.id}
            task={t}
            highlight={t.id === highlightId}
            onStatus={(s) => onStatus(t.id, s)}
            onDelete={() => onDelete(t.id)}
          />
        ))}
        {tasks.length === 0 && <p className="py-6 text-center text-xs text-slate-400">No tasks</p>}
      </div>
    </section>
  );
}
