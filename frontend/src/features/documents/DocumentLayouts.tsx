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
  { key: "problem", label: "Problem" },
  { key: "customer_segments", label: "Customer segments" },
  { key: "unique_value_proposition", label: "Unique value proposition" },
  { key: "solution", label: "Solution" },
  { key: "channels", label: "Channels" },
  { key: "revenue_streams", label: "Revenue streams" },
  { key: "cost_structure", label: "Cost structure" },
  { key: "key_metrics", label: "Key metrics" },
  { key: "unfair_advantage", label: "Unfair advantage" }
];

const BMC_FIELDS: FieldCard[] = [
  { key: "key_partners", label: "Key partners" },
  { key: "key_activities", label: "Key activities" },
  { key: "key_resources", label: "Key resources" },
  { key: "value_propositions", label: "Value propositions" },
  { key: "customer_relationships", label: "Customer relationships" },
  { key: "channels", label: "Channels" },
  { key: "customer_segments", label: "Customer segments" },
  { key: "cost_structure", label: "Cost structure" },
  { key: "revenue_streams", label: "Revenue streams" }
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
    <div className="lean-canvas-grid" aria-label="Lean Canvas blocks">
      {LEAN_CANVAS_FIELDS.map((field) => (
        <DocumentBlock label={field.label} value={textValue(content[field.key])} key={field.key} />
      ))}
    </div>
  );
}

export function BmcLayout({ content }: { content: Record<string, unknown> }) {
  return (
    <div className="bmc-grid" aria-label="Business Model Canvas blocks">
      {BMC_FIELDS.map((field) => (
        <DocumentBlock label={field.label} value={textValue(content[field.key])} key={field.key} />
      ))}
    </div>
  );
}

export function SwotLayout({ content }: { content: Record<string, unknown> }) {
  const groups = [
    { key: "strengths", label: "Strengths" },
    { key: "weaknesses", label: "Weaknesses" },
    { key: "opportunities", label: "Opportunities" },
    { key: "threats", label: "Threats" }
  ];

  return (
    <div className="swot-grid" aria-label="SWOT groups">
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
      <DocumentBlock label="MVP scope" value={textValue(content.mvp_scope)} />

      <section className="document-block">
        <h4>Prioritized features</h4>
        <div className="feature-table" role="table" aria-label="Prioritized feature list">
          <div className="feature-row feature-row-heading" role="row">
            <span role="columnheader">Feature</span>
            <span role="columnheader">Priority</span>
            <span role="columnheader">Effort</span>
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
            <p className="document-muted">No prioritized features yet.</p>
          )}
        </div>
      </section>

      <section className="document-block">
        <h4>Milestone roadmap</h4>
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
          <p className="document-muted">No milestones yet.</p>
        )}
      </section>
    </div>
  );
}

export function MarketingLayout({ content }: { content: Record<string, unknown> }) {
  return (
    <div className="document-stack">
      <DocumentBlock label="Target audience" value={textValue(content.target_audience)} />
      <section className="document-block">
        <h4>Channels</h4>
        <DocumentList values={stringList(content.channels)} />
      </section>
      <DocumentBlock label="Key messages" value={textValue(content.key_messages)} />
      <DocumentBlock label="Estimated budget" value={textValue(content.budget_estimate)} />
    </div>
  );
}

export function FundingLayout({ content }: { content: Record<string, unknown> }) {
  const slides = objectList(content.pitch_outline);

  return (
    <div className="document-stack">
      <section className="document-block">
        <h4>Pitch outline</h4>
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
          <p className="document-muted">No pitch outline yet.</p>
        )}
      </section>
      <DocumentBlock label="Valuation notes" value={textValue(content.valuation_notes)} />
      <DocumentBlock
        label="Recommended funding stage"
        value={textValue(content.funding_stage_recommendation)}
      />
    </div>
  );
}

function DocumentBlock({ label, value }: { label: string; value: string }) {
  return (
    <section className="document-block">
      <h4>{label}</h4>
      <p>{value || "No information yet."}</p>
    </section>
  );
}

function DocumentList({ values }: { values: string[] }) {
  if (values.length === 0) {
    return <p className="document-muted">No information yet.</p>;
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
