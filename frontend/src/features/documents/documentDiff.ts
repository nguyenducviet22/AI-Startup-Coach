export type DocumentDiff = {
  field: string;
  kind: "changed" | "list";
  before: string[];
  after: string[];
  added?: string[];
  removed?: string[];
};

export function diffDocumentContent(
  beforeContent: Record<string, unknown>,
  afterContent: Record<string, unknown>
): DocumentDiff[] {
  const fields = [...new Set([...Object.keys(beforeContent), ...Object.keys(afterContent)])];
  const changes: DocumentDiff[] = [];
  for (const field of fields) {
    const beforeValue = beforeContent[field];
    const afterValue = afterContent[field];
    const before = normalizeValue(beforeValue);
    const after = normalizeValue(afterValue);
    if (JSON.stringify(before) === JSON.stringify(after)) continue;
    if (Array.isArray(beforeValue) && Array.isArray(afterValue)) {
      changes.push({
        field,
        kind: "list",
        before,
        after,
        added: after.filter((item) => !before.includes(item)),
        removed: before.filter((item) => !after.includes(item))
      });
      continue;
    }
    changes.push({ field, kind: "changed", before, after });
  }
  return changes;
}

function normalizeValue(value: unknown): string[] {
  if (value === null || value === undefined || value === "") return [];
  if (Array.isArray(value)) return value.map(formatValue).filter(Boolean);
  return [formatValue(value)].filter(Boolean);
}

function formatValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (value && typeof value === "object") {
    return Object.values(value as Record<string, unknown>).map(formatValue).filter(Boolean).join(" · ");
  }
  return "";
}
