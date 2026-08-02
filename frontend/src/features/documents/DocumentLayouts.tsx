import type { DocumentType, StartupDocument } from "../../api/documents";

type DocumentLayoutProps = {
  docType: DocumentType;
  document: StartupDocument;
};

type FieldCard = {
  key: string;
  label: string;
};

const LEAN_CANVAS_FIELDS: FieldCard[] = [
  { key: "problem", label: "Vấn đề" },
  { key: "customer_segments", label: "Phân khúc khách hàng" },
  { key: "unique_value_proposition", label: "Giá trị khác biệt" },
  { key: "solution", label: "Giải pháp" },
  { key: "channels", label: "Kênh tiếp cận" },
  { key: "revenue_streams", label: "Dòng doanh thu" },
  { key: "cost_structure", label: "Cơ cấu chi phí" },
  { key: "key_metrics", label: "Chỉ số chính" },
  { key: "unfair_advantage", label: "Lợi thế khó sao chép" }
];

const BMC_FIELDS: FieldCard[] = [
  { key: "key_partners", label: "Đối tác chính" },
  { key: "key_activities", label: "Hoạt động chính" },
  { key: "key_resources", label: "Nguồn lực chính" },
  { key: "value_propositions", label: "Giá trị cung cấp" },
  { key: "customer_relationships", label: "Quan hệ khách hàng" },
  { key: "channels", label: "Kênh phân phối" },
  { key: "customer_segments", label: "Phân khúc khách hàng" },
  { key: "cost_structure", label: "Cơ cấu chi phí" },
  { key: "revenue_streams", label: "Dòng doanh thu" }
];

export function DocumentLayout({ docType, document }: DocumentLayoutProps) {
  if (docType === "lean_canvas") {
    return <LeanCanvasLayout content={document.content} />;
  }
  if (docType === "bmc") {
    return <BmcLayout content={document.content} />;
  }
  if (docType === "swot") {
    return <SwotLayout content={document.content} />;
  }
  if (docType === "product_plan") {
    return <ProductPlanLayout content={document.content} />;
  }
  if (docType === "marketing") {
    return <MarketingLayout content={document.content} />;
  }
  return <FundingLayout content={document.content} />;
}

export function LeanCanvasLayout({ content }: { content: Record<string, unknown> }) {
  return (
    <div className="lean-canvas-grid" aria-label="Các khối Lean Canvas">
      {LEAN_CANVAS_FIELDS.map((field) => (
        <DocumentBlock label={field.label} value={textValue(content[field.key])} key={field.key} />
      ))}
    </div>
  );
}

export function BmcLayout({ content }: { content: Record<string, unknown> }) {
  return (
    <div className="bmc-grid" aria-label="Các khối Business Model Canvas">
      {BMC_FIELDS.map((field) => (
        <DocumentBlock label={field.label} value={textValue(content[field.key])} key={field.key} />
      ))}
    </div>
  );
}

export function SwotLayout({ content }: { content: Record<string, unknown> }) {
  const groups = [
    { key: "strengths", label: "Điểm mạnh" },
    { key: "weaknesses", label: "Điểm yếu" },
    { key: "opportunities", label: "Cơ hội" },
    { key: "threats", label: "Thách thức" }
  ];

  return (
    <div className="swot-grid" aria-label="Các nhóm SWOT">
      {groups.map((group) => (
        <section className="document-block swot-group" key={group.key}>
          <h4>{group.label}</h4>
          <DocumentList values={stringList(content[group.key])} />
        </section>
      ))}
    </div>
  );
}

export function ProductPlanLayout({ content }: { content: Record<string, unknown> }) {
  const features = objectList(content.features);
  const timeline = objectList(content.timeline);

  return (
    <div className="document-stack">
      <DocumentBlock label="Phạm vi MVP" value={textValue(content.mvp_scope)} />

      <section className="document-block">
        <h4>Tính năng ưu tiên</h4>
        <div className="feature-table" role="table" aria-label="Danh sách tính năng ưu tiên">
          <div className="feature-row feature-row-heading" role="row">
            <span role="columnheader">Tính năng</span>
            <span role="columnheader">Ưu tiên</span>
            <span role="columnheader">Nguồn lực</span>
          </div>
          {features.length > 0 ? (
            features.map((feature, index) => (
              <div className="feature-row" role="row" key={`${textValue(feature.name)}-${index}`}>
                <span role="cell">{textValue(feature.name)}</span>
                <span role="cell">{textValue(feature.priority)}</span>
                <span role="cell">{textValue(feature.effort)}</span>
              </div>
            ))
          ) : (
            <p className="document-muted">Chưa có tính năng được ưu tiên.</p>
          )}
        </div>
      </section>

      <section className="document-block">
        <h4>Lộ trình cột mốc</h4>
        {timeline.length > 0 ? (
          <ol className="timeline-list">
            {timeline.map((item, index) => (
              <li key={`${textValue(item.milestone)}-${index}`}>
                <strong>{textValue(item.milestone)}</strong>
                <span>{textValue(item.target_date)}</span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="document-muted">Chưa có cột mốc.</p>
        )}
      </section>
    </div>
  );
}

export function MarketingLayout({ content }: { content: Record<string, unknown> }) {
  return (
    <div className="document-stack">
      <DocumentBlock label="Khách hàng mục tiêu" value={textValue(content.target_audience)} />
      <section className="document-block">
        <h4>Kênh tiếp cận</h4>
        <DocumentList values={stringList(content.channels)} />
      </section>
      <DocumentBlock label="Thông điệp chính" value={textValue(content.key_messages)} />
      <DocumentBlock label="Ngân sách dự kiến" value={textValue(content.budget_estimate)} />
    </div>
  );
}

export function FundingLayout({ content }: { content: Record<string, unknown> }) {
  const slides = objectList(content.pitch_outline);

  return (
    <div className="document-stack">
      <section className="document-block">
        <h4>Dàn ý gọi vốn</h4>
        {slides.length > 0 ? (
          <ol className="pitch-list">
            {slides.map((slide, index) => (
              <li key={`${textValue(slide.slide_title)}-${index}`}>
                <strong>{textValue(slide.slide_title)}</strong>
                <p>{textValue(slide.content)}</p>
              </li>
            ))}
          </ol>
        ) : (
          <p className="document-muted">Chưa có dàn ý gọi vốn.</p>
        )}
      </section>
      <DocumentBlock label="Ghi chú định giá" value={textValue(content.valuation_notes)} />
      <DocumentBlock
        label="Đề xuất giai đoạn gọi vốn"
        value={textValue(content.funding_stage_recommendation)}
      />
    </div>
  );
}

function DocumentBlock({ label, value }: { label: string; value: string }) {
  return (
    <section className="document-block">
      <h4>{label}</h4>
      <p>{value || "Chưa có thông tin."}</p>
    </section>
  );
}

function DocumentList({ values }: { values: string[] }) {
  if (values.length === 0) {
    return <p className="document-muted">Chưa có thông tin.</p>;
  }

  return (
    <ul>
      {values.map((value, index) => (
        <li key={`${value}-${index}`}>{value}</li>
      ))}
    </ul>
  );
}

function textValue(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return "";
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
}

function objectList(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is Record<string, unknown> => item !== null && typeof item === "object");
}
