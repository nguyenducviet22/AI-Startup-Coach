export function Skeleton({ lines = 3, compact = false }: { lines?: number; compact?: boolean }) {
  return (
    <div className={compact ? "skeleton-stack skeleton-compact" : "skeleton-stack"} aria-label="Đang tải" aria-busy="true">
      {Array.from({ length: lines }, (_, index) => (
        <span className="skeleton-line" key={index} />
      ))}
    </div>
  );
}
