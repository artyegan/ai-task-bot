// Types mirror the backend's Pydantic schemas. Every task carries its owner.

export type TaskStatus = "pending" | "in_progress" | "completed";
export type TaskSource = "text" | "voice";

export interface User {
  id: number;
  telegram_id: number;
  username: string | null;
  first_name: string | null;
}

export interface Task {
  id: number;
  number: number;
  title: string;
  description: string | null;
  status: TaskStatus;
  source: TaskSource;
  user: User;
  telegram_message_id: number | null;
  created_at: string;
  updated_at: string;
}

export type TaskEvent =
  | { type: "task.created"; task: Task; ts: string }
  | { type: "task.updated"; task: Task; ts: string }
  | { type: "task.deleted"; task_id: number; ts: string }
  | { type: "voice.failed"; voice_job_id: number; user_id: number; error: string; ts: string };

export const STATUSES: TaskStatus[] = ["pending", "in_progress", "completed"];
export const STATUS_LABEL: Record<TaskStatus, string> = {
  pending: "Pending",
  in_progress: "In Progress",
  completed: "Completed",
};

/** Failure codes from the worker (voice_jobs.error) → what to tell the viewer. */
export const VOICE_FAILURE_LABEL: Record<string, string> = {
  file_too_large: "the file was too large",
  download_failed: "the audio could not be downloaded",
  transcription_failed: "transcription failed",
  transcription_empty: "no speech was detected",
  timed_out: "it took too long",
  internal_error: "an internal error occurred",
};

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const err = body?.error ?? { code: "http_error", message: res.statusText };
    throw new ApiError(err.code, err.message, res.status);
  }
  return body as T;
}

export const api = {
  listTasks: () => request<{ items: Task[]; total: number }>("/api/tasks?limit=500"),
  listUsers: () => request<{ items: User[] }>("/api/users"),
  createTask: (body: { title: string; user_id: number; description?: string }) =>
    request<Task>("/api/tasks", { method: "POST", body: JSON.stringify(body) }),
  updateTask: (id: number, patch: Partial<Pick<Task, "status" | "title" | "description">>) =>
    request<Task>(`/api/tasks/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deleteTask: (id: number) => request<void>(`/api/tasks/${id}`, { method: "DELETE" }),
};

export function displayName(user: User): string {
  return user.username ? `@${user.username}` : (user.first_name ?? `user ${user.telegram_id}`);
}

export function timeAgo(iso: string, now = Date.now()): string {
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (s < 60) return "just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}
