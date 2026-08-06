import { apiRequest, apiUrl } from "./client";
import type { DocumentExportFormat } from "./documents";

export type ReportSection = { key: string; title: string; available: boolean; content: Record<string, unknown> };
export type StartupReport = { startup_id: string; startup_name: string; sections: ReportSection[] };

export function getStartupReport(startupId: string): Promise<StartupReport> {
  return apiRequest<StartupReport>(`/startups/${startupId}/report`);
}

export async function downloadStartupReport(startupId: string, format: DocumentExportFormat, sections: string[]): Promise<void> {
  const params = new URLSearchParams({ format, sections: sections.join(",") });
  const response = await fetch(apiUrl(`/startups/${startupId}/report/export?${params.toString()}`), {
    headers: { Accept: format === "pdf" ? "application/pdf" : "application/vnd.openxmlformats-officedocument.wordprocessingml.document" }
  });
  if (!response.ok) throw new Error(`Unable to download report (${response.status}).`);
  const blobUrl = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = blobUrl;
  link.download = response.headers.get("Content-Disposition")?.match(/filename="?([^";]+)"?/i)?.[1] ?? `startup-report.${format}`;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(blobUrl);
}

export async function downloadPitchDeck(startupId: string): Promise<void> {
  const response = await fetch(apiUrl(`/startups/${startupId}/pitch-deck/export?format=pdf`), { headers: { Accept: "application/pdf" } });
  if (!response.ok) throw new Error(`Unable to download pitch deck (${response.status}).`);
  const blobUrl = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = blobUrl;
  link.download = response.headers.get("Content-Disposition")?.match(/filename="?([^";]+)"?/i)?.[1] ?? "pitch-deck.pdf";
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(blobUrl);
}
