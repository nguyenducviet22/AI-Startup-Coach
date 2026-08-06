import { useEffect, useState } from "react";

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
  const [isCollapsed, setIsCollapsed] = useState(false);

  useEffect(() => {
    setIsCollapsed(false);
  }, [readiness, currentStage]);

  if (!readiness || currentStage === "completed") {
    return null;
  }

  const nextLabel = nextStageLabel(currentStage);
  if (readiness.ready && nextLabel) {
    return (
      <section className="readiness-prompt readiness-ready" aria-label="Stage readiness">
        <div>
          <h3>Ready for the next stage</h3>
          <p>Your Coach has enough information to continue.</p>
        </div>
        <button type="button" className="primary-button" onClick={onAdvanceStage} disabled={isAdvancing}>
          {isAdvancing ? "Advancing..." : `Continue to ${nextLabel}`}
        </button>
      </section>
    );
  }

  return (
    <section className="readiness-prompt" aria-label="Stage readiness">
      <div className="readiness-prompt-content">
        <h3>More information needed</h3>
        {!isCollapsed && readiness.missing_fields.length > 0 ? (
          <ul>
            {readiness.missing_fields.map((field) => (
              <li key={field}>{readinessFieldLabel(field)}</li>
            ))}
          </ul>
        ) : !isCollapsed ? (
          <p>Your Coach needs a few more details before suggesting the next stage.</p>
        ) : null}
      </div>
      <CollapseButton isCollapsed={isCollapsed} onToggle={() => setIsCollapsed((collapsed) => !collapsed)} />
    </section>
  );
}

type CollapseButtonProps = {
  isCollapsed: boolean;
  onToggle: () => void;
};

function CollapseButton({ isCollapsed, onToggle }: CollapseButtonProps) {
  return (
    <button
      type="button"
      className="readiness-collapse"
      aria-label={isCollapsed ? "Expand readiness notice" : "Collapse readiness notice"}
      aria-expanded={!isCollapsed}
      onClick={onToggle}
    >
      {isCollapsed ? "+" : "−"}
    </button>
  );
}

const READINESS_FIELD_LABELS: Record<string, string> = {
  problem: "Customer problem",
  customer_segments: "Customer segments",
  unique_value_proposition: "Unique value proposition",
  solution: "Solution",
  channels: "Channels",
  revenue_streams: "Revenue streams",
  cost_structure: "Cost structure",
  key_metrics: "Key metrics",
  unfair_advantage: "Unfair advantage"
};

function readinessFieldLabel(field: string): string {
  return READINESS_FIELD_LABELS[field] ?? field.replaceAll("_", " ");
}
