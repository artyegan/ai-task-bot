import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Task, type TaskEvent, type TaskStatus } from "../lib/api";
import { applyEvent } from "../lib/events";

const TASKS = ["tasks"] as const;

export function useTasks() {
  const qc = useQueryClient();

  const query = useQuery({
    queryKey: TASKS,
    queryFn: async () => (await api.listTasks()).items,
    staleTime: Infinity, // the WebSocket keeps it fresh; refetch happens on reconnect
  });
  const users = useQuery({ queryKey: ["users"], queryFn: async () => (await api.listUsers()).items });

  const apply = (event: TaskEvent) => {
    qc.setQueryData<Task[]>(TASKS, (old) => applyEvent(old ?? [], event));
    if (event.type === "task.created") void users.refetch(); // a new user may have appeared
  };

  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: TaskStatus }) =>
      api.updateTask(id, { status }),
    onMutate: async ({ id, status }) => {
      await qc.cancelQueries({ queryKey: TASKS });
      const previous = qc.getQueryData<Task[]>(TASKS);
      qc.setQueryData<Task[]>(TASKS, (old) =>
        (old ?? []).map((t) => (t.id === id ? { ...t, status } : t)),
      );
      return { previous };
    },
    onError: (_err, _vars, ctx) => ctx?.previous && qc.setQueryData(TASKS, ctx.previous),
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.deleteTask(id),
    onSuccess: (_d, id) =>
      qc.setQueryData<Task[]>(TASKS, (old) => (old ?? []).filter((t) => t.id !== id)),
  });

  const create = useMutation({
    mutationFn: (body: { title: string; user_id: number }) => api.createTask(body),
    onSuccess: (task) => apply({ type: "task.created", task, ts: task.created_at }),
  });

  return {
    tasks: query.data ?? [],
    users: users.data ?? [],
    isLoading: query.isLoading,
    error: query.error,
    refetch: () => void query.refetch(),
    apply,
    setStatus,
    remove,
    create,
  };
}
