import { useCallback, useEffect, useState } from "react";
import { Board } from "./components/Board";
import { ListView } from "./components/ListView";
import { Toasts, type ToastItem } from "./components/Toast";
import { Toolbar } from "./components/Toolbar";
import { useTaskSocket } from "./hooks/useTaskSocket";
import { useTasks } from "./hooks/useTasks";
import { displayName, type TaskEvent, type TaskStatus } from "./lib/api";

type View = "board" | "list";

export default function App() {
  const { tasks, users, isLoading, error, refetch, apply, setStatus, remove, create } = useTasks();
  const [view, setView] = useState<View>(() => (localStorage.getItem("view") as View) || "board");
  const [userFilter, setUserFilter] = useState<number | "all">("all");
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [highlightId, setHighlightId] = useState<number | null>(null);

  const toast = useCallback((text: string, kind: ToastItem["kind"] = "info") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, text, kind }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 5000);
  }, []);

  const onEvent = useCallback(
    (event: TaskEvent) => {
      apply(event);
      if (event.type === "task.created") {
        setHighlightId(event.task.id);
        window.setTimeout(() => setHighlightId(null), 3000);
        toast(
          `${event.task.source === "voice" ? "🎤 " : ""}New task from ${displayName(event.task.user)}: ${event.task.title}`,
        );
      }
    },
    [apply, toast],
  );
  const socket = useTaskSocket(onEvent, refetch);

  useEffect(() => localStorage.setItem("view", view), [view]);

  const onStatus = (id: number, status: TaskStatus) =>
    setStatus.mutate({ id, status }, { onError: (e) => toast(`Update failed: ${e.message}`, "error") });
  const onDelete = (id: number) => {
    const t = tasks.find((x) => x.id === id);
    if (t && confirm(`Delete task #${t.number} "${t.title}"?`))
      remove.mutate(id, { onError: (e) => toast(`Delete failed: ${e.message}`, "error") });
  };
  const onCreate = (title: string, user_id: number) =>
    create.mutateAsync({ title, user_id }).catch((e) => toast(`Create failed: ${e.message}`, "error"));

  const visible = userFilter === "all" ? tasks : tasks.filter((t) => t.user.id === userFilter);

  return (
    <main className="mx-auto max-w-6xl p-4">
      <Toolbar
        view={view}
        onView={setView}
        users={users}
        userFilter={userFilter}
        onUserFilter={setUserFilter}
        socket={socket}
        onCreate={onCreate}
      />
      {error && (
        <p className="mb-4 rounded bg-red-50 p-3 text-sm text-red-700">
          Could not load tasks: {error.message}
        </p>
      )}
      {isLoading ? (
        <p className="py-12 text-center text-slate-400">Loading…</p>
      ) : view === "board" ? (
        <Board tasks={visible} highlightId={highlightId} onStatus={onStatus} onDelete={onDelete} />
      ) : (
        <ListView tasks={visible} highlightId={highlightId} onStatus={onStatus} onDelete={onDelete} />
      )}
      <Toasts items={toasts} onClose={(id) => setToasts((t) => t.filter((x) => x.id !== id))} />
    </main>
  );
}
