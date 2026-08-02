import type { StageReadiness } from "../../api/chat";
import type { StageName } from "../../api/startups";
import { nextStageLabel } from "../stages/stageLabels";

type StageReadinessPromptProps = {
  readiness: StageReadiness | null;
  currentStage: StageName;
  isAdvancing?: boolean;
  onAdvanceStage: () => void;
};

export function StageReadinessPrompt({
  readiness,
  currentStage,
  isAdvancing = false,
  onAdvanceStage
}: StageReadinessPromptProps) {
  if (!readiness || currentStage === "completed") {
    return null;
  }

  const nextLabel = nextStageLabel(currentStage);
  if (readiness.ready && nextLabel) {
    return (
      <section className="readiness-prompt readiness-ready" aria-label="Mức độ sẵn sàng của giai đoạn">
        <div>
          <h3>Sẵn sàng cho giai đoạn tiếp theo</h3>
          <p>Coach nhận thấy bạn đã cung cấp đủ thông tin để tiếp tục.</p>
        </div>
        <button type="button" className="primary-button" onClick={onAdvanceStage} disabled={isAdvancing}>
          {isAdvancing ? "Đang chuyển..." : `Tiếp tục đến ${nextLabel}`}
        </button>
      </section>
    );
  }

  return (
    <section className="readiness-prompt" aria-label="Mức độ sẵn sàng của giai đoạn">
      <h3>Cần thêm thông tin</h3>
      {readiness.missing_fields.length > 0 ? (
        <ul>
          {readiness.missing_fields.map((field) => (
            <li key={field}>{readinessFieldLabel(field)}</li>
          ))}
        </ul>
      ) : (
        <p>Coach cần thêm một vài chi tiết trước khi đề xuất chuyển giai đoạn.</p>
      )}
    </section>
  );
}

const READINESS_FIELD_LABELS: Record<string, string> = {
  problem: "Vấn đề khách hàng",
  customer_segments: "Phân khúc khách hàng",
  unique_value_proposition: "Giá trị khác biệt",
  solution: "Giải pháp",
  channels: "Kênh tiếp cận",
  revenue_streams: "Dòng doanh thu",
  cost_structure: "Cơ cấu chi phí",
  key_metrics: "Chỉ số chính",
  unfair_advantage: "Lợi thế khó sao chép"
};

function readinessFieldLabel(field: string): string {
  return READINESS_FIELD_LABELS[field] ?? field.replaceAll("_", " ");
}
