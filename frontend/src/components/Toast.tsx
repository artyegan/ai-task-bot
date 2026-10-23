export interface ToastItem {
  id: number;
  text: string;
  kind: "info" | "error";
}

export function Toasts({ items, onClose }: { items: ToastItem[]; onClose: (id: number) => void }) {
  return (
    <div className="fixed bottom-4 right-4 z-50 flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2">
      {items.map((t) => (
        <button
          key={t.id}
          onClick={() => onClose(t.id)}
          className={`rounded-lg px-4 py-3 text-left text-sm text-white shadow-lg ${
            t.kind === "error" ? "bg-red-600" : "bg-slate-800"
          }`}
        >
          {t.text}
        </button>
      ))}
    </div>
  );
}
