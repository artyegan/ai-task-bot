import { useState, type FormEvent } from "react";
import { displayName, type User } from "../lib/api";
import type { SocketStatus } from "../hooks/useTaskSocket";

interface Props {
  view: "board" | "list";
  onView: (v: "board" | "list") => void;
  users: User[];
  userFilter: number | "all";
  onUserFilter: (v: number | "all") => void;
  socket: SocketStatus;
  onCreate: (title: string, userId: number) => Promise<unknown>;
}

const DOT: Record<SocketStatus, string> = {
  open: "bg-emerald-500",
  connecting: "bg-amber-400",
  reconnecting: "bg-red-500 animate-pulse",
};
const LABEL: Record<SocketStatus, string> = {
  open: "Live",
  connecting: "Connecting",
  reconnecting: "Reconnecting",
};

export function Toolbar({ view, onView, users, userFilter, onUserFilter, socket, onCreate }: Props) {
  const [title, setTitle] = useState("");
  const [owner, setOwner] = useState<number | "">("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!title.trim() || owner === "") return;
    setBusy(true);
    try {
      await onCreate(title.trim(), owner);
      setTitle("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <header className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-bold">AI Task Bot</h1>
        <span className="flex items-center gap-1.5 text-xs text-slate-500" title="WebSocket status">
          <span className={`inline-block h-2 w-2 rounded-full ${DOT[socket]}`} />
          {LABEL[socket]}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <form onSubmit={submit} className="flex items-center gap-1">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="New task…"
            className="w-40 rounded border border-slate-300 px-2 py-1 text-sm md:w-56"
          />
          <select
            value={owner}
            onChange={(e) => setOwner(e.target.value === "" ? "" : Number(e.target.value))}
            className="rounded border border-slate-300 px-2 py-1 text-sm"
            aria-label="Owner"
          >
            <option value="">Owner…</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {displayName(u)}
              </option>
            ))}
          </select>
          <button
            disabled={busy || !title.trim() || owner === ""}
            className="rounded bg-slate-900 px-3 py-1 text-sm text-white disabled:opacity-40"
          >
            Add
          </button>
        </form>

        <select
          value={userFilter}
          onChange={(e) => onUserFilter(e.target.value === "all" ? "all" : Number(e.target.value))}
          className="rounded border border-slate-300 px-2 py-1 text-sm"
          aria-label="Filter by user"
        >
          <option value="all">All users</option>
          {users.map((u) => (
            <option key={u.id} value={u.id}>
              {displayName(u)}
            </option>
          ))}
        </select>

        <div className="flex overflow-hidden rounded border border-slate-300 text-sm">
          {(["board", "list"] as const).map((v) => (
            <button
              key={v}
              onClick={() => onView(v)}
              className={`px-3 py-1 ${view === v ? "bg-slate-900 text-white" : "bg-white"}`}
            >
              {v === "board" ? "Board" : "List"}
            </button>
          ))}
        </div>
      </div>
    </header>
  );
}
