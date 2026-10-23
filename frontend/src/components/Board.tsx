import { DndContext, PointerSensor, useSensor, useSensors, type DragEndEvent } from "@dnd-kit/core";
import { STATUSES, type Task, type TaskStatus } from "../lib/api";
import { Column } from "./Column";

interface Props {
  tasks: Task[];
  highlightId: number | null;
  onStatus: (id: number, status: TaskStatus) => void;
  onDelete: (id: number) => void;
}

export function Board({ tasks, highlightId, onStatus, onDelete }: Props) {
  // A small activation distance keeps the card's buttons clickable.
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));

  const onDragEnd = (e: DragEndEvent) => {
    const target = e.over?.id as TaskStatus | undefined;
    const from = e.active.data.current?.status as TaskStatus | undefined;
    if (target && from && target !== from) onStatus(Number(e.active.id), target);
  };

  return (
    <DndContext sensors={sensors} onDragEnd={onDragEnd}>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {STATUSES.map((status) => (
          <Column
            key={status}
            status={status}
            tasks={tasks.filter((t) => t.status === status)}
            highlightId={highlightId}
            onStatus={onStatus}
            onDelete={onDelete}
          />
        ))}
      </div>
    </DndContext>
  );
}
