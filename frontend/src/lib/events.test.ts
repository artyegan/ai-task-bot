import { describe, expect, it } from "vitest";
import { applyEvent } from "./events";
import type { Task } from "./api";
import { timeAgo } from "./api";

const user = { id: 1, telegram_id: 1, username: "alice", first_name: "Alice" };
const task = (id: number, status: Task["status"] = "pending"): Task => ({
  id,
  number: id,
  title: `t${id}`,
  description: null,
  status,
  source: "text",
  user,
  telegram_message_id: null,
  created_at: "2026-10-22T10:00:00.000Z",
  updated_at: "2026-10-22T10:00:00.000Z",
});

describe("applyEvent", () => {
  it("prepends created tasks and ignores duplicates", () => {
    const list = applyEvent([task(1)], { type: "task.created", task: task(2), ts: "" });
    expect(list.map((t) => t.id)).toEqual([2, 1]);
    expect(applyEvent(list, { type: "task.created", task: task(2), ts: "" })).toBe(list);
  });

  it("replaces updated tasks in place, or inserts unknown ones", () => {
    const list = applyEvent([task(1), task(2)], {
      type: "task.updated",
      task: task(2, "completed"),
      ts: "",
    });
    expect(list.map((t) => [t.id, t.status])).toEqual([
      [1, "pending"],
      [2, "completed"],
    ]);
    expect(applyEvent([], { type: "task.updated", task: task(9), ts: "" })).toHaveLength(1);
  });

  it("removes deleted tasks and ignores voice failures", () => {
    const list = [task(1), task(2)];
    expect(applyEvent(list, { type: "task.deleted", task_id: 1, ts: "" }).map((t) => t.id)).toEqual(
      [2],
    );
    expect(
      applyEvent(list, { type: "voice.failed", voice_job_id: 1, user_id: 1, error: "x", ts: "" }),
    ).toBe(list);
  });
});

describe("timeAgo", () => {
  const now = Date.parse("2026-10-22T12:00:00Z");
  it("formats relative times", () => {
    expect(timeAgo("2026-10-22T11:59:50Z", now)).toBe("just now");
    expect(timeAgo("2026-10-22T11:45:00Z", now)).toBe("15m ago");
    expect(timeAgo("2026-10-22T09:00:00Z", now)).toBe("3h ago");
    expect(timeAgo("2026-10-20T12:00:00Z", now)).toBe("2d ago");
  });
});
