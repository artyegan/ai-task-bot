import { STATUSES, STATUS_LABEL, displayName, timeAgo, type Task, type TaskStatus } from "../lib/api";

interface Props {
  tasks: Task[];
  highlightId: number | null;
  onStatus: (id: number, status: TaskStatus) => void;
  onDelete: (id: number) => void;
}

const BADGE: Record<TaskStatus, string> = {
  pending: "bg-amber-100 text-amber-800",
  in_progress: "bg-sky-100 text-sky-800",
  completed: "bg-emerald-100 text-emerald-800",
};

export function ListView({ tasks, highlightId, onStatus, onDelete }: Props) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-3 py-2">#</th>
            <th className="px-3 py-2">Task</th>
            <th className="px-3 py-2">Owner</th>
            <th className="px-3 py-2">Status</th>
            <th className="px-3 py-2">Created</th>
            <th className="px-3 py-2" />
          </tr>
        </thead>
        <tbody>
          {tasks.map((t) => (
            <tr
              key={t.id}
              className={`border-t border-slate-100 ${t.id === highlightId ? "bg-emerald-50" : ""}`}
            >
              <td className="px-3 py-2 text-slate-500">{t.number}</td>
              <td className="px-3 py-2">
                {t.source === "voice" && <span className="mr-1">🎤</span>}
                {t.title}
              </td>
              <td className="px-3 py-2 text-slate-600">{displayName(t.user)}</td>
              <td className="px-3 py-2">
                <select
                  value={t.status}
                  onChange={(e) => onStatus(t.id, e.target.value as TaskStatus)}
                  className={`rounded-full border-0 px-2 py-1 text-xs font-medium ${BADGE[t.status]}`}
                >
                  {STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {STATUS_LABEL[s]}
                    </option>
                  ))}
                </select>
              </td>
              <td className="px-3 py-2 text-slate-500">{timeAgo(t.created_at)}</td>
              <td className="px-3 py-2 text-right">
                <button
                  onClick={() => onDelete(t.id)}
                  className="rounded px-2 py-0.5 text-xs text-slate-400 hover:bg-red-50 hover:text-red-600"
                  aria-label={`Delete task ${t.number}`}
                >
                  ✕
                </button>
              </td>
            </tr>
          ))}
          {tasks.length === 0 && (
            <tr>
              <td colSpan={6} className="px-3 py-8 text-center text-slate-400">
                No tasks yet. Send one to the Telegram bot.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
