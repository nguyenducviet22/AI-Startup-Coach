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
          <p className="eyebrow">Lộ trình</p>
          <h2 id="stage-heading">{isCompleted ? "Hoàn thành hành trình" : STAGE_LABELS[currentStage]}</h2>
          <p className="section-description">Mỗi giai đoạn giúp bạn kiểm chứng một phần quan trọng của startup.</p>
        </div>
        {isCompleted ? <span className="status-pill">Đã hoàn thành</span> : null}
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
            {isAdvancing ? "Đang chuyển..." : `Tiếp tục đến ${nextLabel}`}
          </button>
        ) : (
          <p className="stage-complete-copy">Bạn đã hoàn thành lộ trình coaching có hướng dẫn.</p>
        )}

        {backOptions.length > 0 ? (
          <form className="set-stage-form" onSubmit={handleSetStage}>
            <label>
              Xem lại giai đoạn
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
              {isSettingStage ? "Đang cập nhật..." : "Quay lại"}
            </button>
          </form>
        ) : null}
      </div>
    </section>
  );
}
