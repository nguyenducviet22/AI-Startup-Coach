import { FormEvent, useMemo, useState } from "react";

import type { StageName } from "../../api/startups";
import { nextStageLabel, priorStages, STAGE_LABELS } from "./stageLabels";
import { StageStepper } from "./StageStepper";

type StageControlsProps = {
  currentStage: StageName;
  isAdvancing?: boolean;
  isSettingStage?: boolean;
  onAdvanceStage: () => void;
  onSetStage: (stage: StageName) => void;
};

export function StageControls({
  currentStage,
  isAdvancing = false,
  isSettingStage = false,
  onAdvanceStage,
  onSetStage
}: StageControlsProps) {
  const backOptions = useMemo(() => priorStages(currentStage), [currentStage]);
  const [targetStage, setTargetStage] = useState<StageName | "">(backOptions.at(-1) ?? "");
  const nextLabel = nextStageLabel(currentStage);
  const isCompleted = currentStage === "completed";

  function handleSetStage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!targetStage) {
      return;
    }
    onSetStage(targetStage);
  }

  return (
    <section className="workspace-section" aria-labelledby="stage-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Stage</p>
          <h2 id="stage-heading">{isCompleted ? "Coaching complete" : STAGE_LABELS[currentStage]}</h2>
        </div>
        {isCompleted ? <span className="status-pill">Completed</span> : null}
      </div>

      <StageStepper currentStage={currentStage} />

      <div className="stage-actions">
        {!isCompleted && nextLabel ? (
          <button
            type="button"
            className="primary-button"
            onClick={onAdvanceStage}
            disabled={isAdvancing}
          >
            {isAdvancing ? "Advancing..." : `Advance to ${nextLabel}`}
          </button>
        ) : (
          <p className="stage-complete-copy">The guided startup coaching path is complete.</p>
        )}

        {backOptions.length > 0 ? (
          <form className="set-stage-form" onSubmit={handleSetStage}>
            <label>
              Go back to
              <select
                value={targetStage}
                onChange={(event) => setTargetStage(event.target.value as StageName)}
              >
                {backOptions.map((stage) => (
                  <option value={stage} key={stage}>
                    {STAGE_LABELS[stage]}
                  </option>
                ))}
              </select>
            </label>
            <button type="submit" className="secondary-button" disabled={!targetStage || isSettingStage}>
              {isSettingStage ? "Updating..." : "Set stage"}
            </button>
          </form>
        ) : null}
      </div>
    </section>
  );
}
