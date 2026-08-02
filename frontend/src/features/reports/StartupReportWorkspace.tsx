import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import type { DocumentExportFormat } from "../../api/documents";
import { downloadStartupReport, getStartupReport } from "../../api/reports";
import { Skeleton } from "../../components/Skeleton";
import { useToastStore } from "../../stores/toastStore";

export function StartupReportWorkspace({ startupId, onBack }: { startupId: string; onBack?: () => void }) {
  const query = useQuery({ queryKey: ["startup-report", startupId], queryFn: () => getStartupReport(startupId), enabled: Boolean(startupId) });
  const [selected, setSelected] = useState<string[]>([]);
  const [downloading, setDownloading] = useState<DocumentExportFormat | null>(null);
  const showToast = useToastStore((state) => state.showToast);
  useEffect(() => {
    if (query.data) setSelected(query.data.sections.filter((section) => section.available).map((section) => section.key));
  }, [query.data]);

  async function download(format: DocumentExportFormat) {
    setDownloading(format);
    try {
      await downloadStartupReport(startupId, format, selected);
      showToast(`Đã tải hồ sơ dạng ${format.toUpperCase()}.`, "success");
    } catch {
      showToast("Không thể tải hồ sơ. Vui lòng thử lại.", "error");
    } finally {
      setDownloading(null);
    }
  }

  if (query.isLoading) return <section className="workspace-section"><Skeleton lines={6} /></section>;
  if (query.error) return <section className="workspace-section"><p className="form-error">{query.error.message}</p></section>;
  const report = query.data;
  if (!report) return null;
  return <section className="workspace-section startup-report" aria-labelledby="startup-report-heading">
    <div className="section-heading"><div><p className="eyebrow">Hồ sơ tổng hợp</p><h2 id="startup-report-heading">Hồ sơ dự án {report.startup_name}</h2><p className="section-description">Chọn các phần sẽ xuất; bản xem trước và file tải xuống dùng cùng dữ liệu hiện tại.</p></div><div className="document-actions">{onBack ? <button type="button" className="text-button" onClick={onBack}>Quay lại tài liệu</button> : null}<button type="button" className="secondary-button" disabled={!selected.length || downloading !== null} aria-label="Tải hồ sơ DOCX" onClick={() => void download("docx")}>{downloading === "docx" ? "Đang tạo..." : "Tải DOCX"}</button><button type="button" className="primary-button" disabled={!selected.length || downloading !== null} aria-label="Tải hồ sơ PDF" onClick={() => void download("pdf")}>{downloading === "pdf" ? "Đang tạo..." : "Tải PDF"}</button></div></div>
    <div className="report-layout">
      <aside className="report-section-picker" aria-label="Chọn nội dung hồ sơ"><h3>Nội dung hồ sơ</h3>{report.sections.map((section) => <label key={section.key} className={!section.available ? "disabled" : ""}><input type="checkbox" aria-label={section.title} checked={selected.includes(section.key)} disabled={!section.available} onChange={(event) => setSelected((current) => event.target.checked ? [...current, section.key] : current.filter((key) => key !== section.key))} /> <span>{section.title}</span><small>{section.available ? "Sẵn sàng" : "Chưa có dữ liệu"}</small></label>)}</aside>
      <article className="document-page-preview report-preview"><header className="document-page-heading"><p>AI Startup Coach</p><h3>Hồ sơ dự án {report.startup_name}</h3></header>{report.sections.filter((section) => selected.includes(section.key)).map((section) => <section className="report-preview-section" key={section.key}><h3>{section.title}</h3>{renderContent(section.content)}</section>)}</article>
    </div>
  </section>;
}

function renderContent(content: Record<string, unknown>) {
  const entries = Object.entries(content).filter(([, value]) => value !== null && value !== "" && (!Array.isArray(value) || value.length));
  return entries.length ? <dl>{entries.map(([key, value]) => <div key={key}><dt>{formatKey(key)}</dt><dd>{formatValue(value)}</dd></div>)}</dl> : <p className="document-muted">Chưa có thông tin.</p>;
}

function formatKey(key: string) { return key.split("_").map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" "); }
function formatValue(value: unknown): string {
  if (Array.isArray(value)) return value.map((item) => typeof item === "object" && item ? Object.values(item).join(" · ") : String(item)).join("; ");
  if (value && typeof value === "object") return Object.values(value).join(" · ");
  return String(value);
}
