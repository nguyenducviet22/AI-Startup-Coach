import type { StartupDocument } from "../../api/documents";
import { diffDocumentContent } from "./documentDiff";

export function VersionCompare({ older, current, onClose }: { older: StartupDocument; current: StartupDocument; onClose: () => void }) {
  const changes = diffDocumentContent(older.content, current.content);
  return <section className="version-compare" aria-labelledby="version-compare-heading">
    <div className="version-compare-heading">
      <div><p className="eyebrow">Điều gì đã thay đổi?</p><h3 id="version-compare-heading">Phiên bản {older.version} → {current.version}</h3></div>
      <button type="button" className="text-button" onClick={onClose}>Đóng so sánh</button>
    </div>
    {changes.length === 0 ? <p className="document-muted">Không có thay đổi nội dung.</p> : <div className="version-diff-list">
      {changes.map((change) => <article className="version-diff" key={change.field}>
        <h4>{formatField(change.field)}</h4>
        {change.kind === "list" ? <div className="version-diff-list-values">
          {(change.removed ?? []).map((item) => <p className="diff-removed" key={`removed-${item}`}><span aria-hidden="true">−</span> {item}</p>)}
          {(change.added ?? []).map((item) => <p className="diff-added" key={`added-${item}`}><span aria-hidden="true">+</span> {item}</p>)}
        </div> : <div className="version-diff-columns">
          <div><small>Trước</small><p>{change.before.join("; ") || "Chưa có thông tin"}</p></div>
          <div><small>Sau</small><p>{change.after.join("; ") || "Chưa có thông tin"}</p></div>
        </div>}
      </article>)}
    </div>}
  </section>;
}

function formatField(field: string): string {
  return field.split("_").map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ");
}
