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
      <section className="readiness-prompt readiness-ready" aria-label="Stage readiness">
        <div>
          <h3>Ready for the next stage</h3>
          <p>The coach thinks this stage has enough context to move forward.</p>
        </div>
        <button type="button" className="primary-button" onClick={onAdvanceStage} disabled={isAdvancing}>
          {isAdvancing ? "Advancing..." : `Advance to ${nextLabel}`}
        </button>
      </section>
    );
  }

  return (
    <section className="readiness-prompt" aria-label="Stage readiness">
      <h3>More context needed</h3>
      {readiness.missing_fields.length > 0 ? (
        <ul>
          {readiness.missing_fields.map((field) => (
            <li key={field}>{field}</li>
          ))}
        </ul>
      ) : (
        <p>The coach needs a little more detail before recommending the next stage.</p>
      )}
    </section>
  );
}
