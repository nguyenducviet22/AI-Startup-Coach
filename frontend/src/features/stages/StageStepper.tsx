import type { StageName } from "../../api/startups";
import { STAGE_LABELS, STAGES } from "./stageLabels";

type StageStepperProps = {
  currentStage: StageName;
};

export function StageStepper({ currentStage }: StageStepperProps) {
  const isCompleted = currentStage === "completed";
  const currentIndex = isCompleted ? STAGES.length : STAGES.indexOf(currentStage);

  return (
    <div className="stage-stepper" aria-label="Startup stage progress">
      {STAGES.map((stage, index) => {
        const status = index < currentIndex ? "complete" : index === currentIndex ? "current" : "upcoming";
        return (
          <div className={`stage-step stage-step-${status}`} key={stage}>
            <span className="stage-dot" aria-hidden="true" />
            <span>{STAGE_LABELS[stage]}</span>
          </div>
        );
      })}
      <div className={`stage-step stage-step-${isCompleted ? "terminal" : "upcoming"}`}>
        <span className="stage-dot" aria-hidden="true" />
        <span>{STAGE_LABELS.completed}</span>
      </div>
    </div>
  );
}
