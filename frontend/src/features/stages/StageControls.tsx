import { FormEvent, useEffect, useMemo, useState } from "react";

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

  useEffect(() => {
    setTargetStage(backOptions.at(-1) ?? "");
  }, [backOptions]);

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
          <p className="eyebrow">Journey</p>
          <h2 id="stage-heading">{isCompleted ? "Journey completed" : STAGE_LABELS[currentStage]}</h2>
          <p className="section-description">Each stage helps validate an important part of your startup.</p>
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
            {isAdvancing ? "Advancing..." : `Continue to ${nextLabel}`}
          </button>
        ) : (
          <p className="stage-complete-copy">You have completed the guided coaching journey.</p>
        )}

        {backOptions.length > 0 ? (
          <form className="set-stage-form" onSubmit={handleSetStage}>
            <label>
              Review a stage
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
              {isSettingStage ? "Updating..." : "Go back"}
            </button>
          </form>
        ) : null}
      </div>
    </section>
  );
}
