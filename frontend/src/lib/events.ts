import type { Task, TaskEvent } from "./api";

/** Applies one WebSocket event to the task list. Pure, so it is unit-tested. */
export function applyEvent(tasks: Task[], event: TaskEvent): Task[] {
  switch (event.type) {
    case "task.created": {
      if (tasks.some((t) => t.id === event.task.id)) return tasks; // already fetched
      return [event.task, ...tasks];
    }
    case "task.updated": {
      const exists = tasks.some((t) => t.id === event.task.id);
      return exists
        ? tasks.map((t) => (t.id === event.task.id ? event.task : t))
        : [event.task, ...tasks];
    }
    case "task.deleted":
      return tasks.filter((t) => t.id !== event.task_id);
    default:
      return tasks;
  }
}
