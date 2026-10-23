// @vitest-environment jsdom
import { DndContext } from "@dnd-kit/core";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Task } from "../lib/api";
import { TaskCard } from "./TaskCard";
import { ListView } from "./ListView";

const task: Task = {
  id: 7,
  number: 3,
  title: "Buy butter",
  description: null,
  status: "pending",
  source: "voice",
  user: { id: 1, telegram_id: 1, username: "alice", first_name: "Alice" },
  telegram_message_id: null,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

afterEach(cleanup);

describe("TaskCard", () => {
  it("shows title, per-user number, owner and the voice badge", () => {
    render(
      <DndContext>
        <TaskCard task={task} onStatus={() => {}} onDelete={() => {}} />
      </DndContext>,
    );
    expect(screen.getByText("Buy butter")).toBeTruthy();
    expect(screen.getByText(/#3 · @alice/)).toBeTruthy();
    expect(screen.getByLabelText("voice")).toBeTruthy();
  });

  it("offers the two other statuses and reports the chosen one", () => {
    const onStatus = vi.fn();
    render(
      <DndContext>
        <TaskCard task={task} onStatus={onStatus} onDelete={() => {}} />
      </DndContext>,
    );
    expect(screen.queryByText("→ Pending")).toBeNull();
    fireEvent.click(screen.getByText("→ Completed"));
    expect(onStatus).toHaveBeenCalledWith("completed");
  });
});

describe("ListView", () => {
  it("renders a row per task with a status dropdown", () => {
    const onStatus = vi.fn();
    render(<ListView tasks={[task]} highlightId={null} onStatus={onStatus} onDelete={() => {}} />);
    const select = screen.getByDisplayValue("Pending") as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "in_progress" } });
    expect(onStatus).toHaveBeenCalledWith(7, "in_progress");
  });

  it("shows an empty state", () => {
    render(<ListView tasks={[]} highlightId={null} onStatus={() => {}} onDelete={() => {}} />);
    expect(screen.getByText(/No tasks yet/)).toBeTruthy();
  });
});
