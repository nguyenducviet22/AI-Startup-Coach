import type { StageName } from "../../api/startups";

export const STAGES: StageName[] = [
  "idea",
  "lean_canvas",
  "bmc",
  "swot",
  "product_plan",
  "marketing",
  "funding"
];

export const ALL_STAGES: StageName[] = [...STAGES, "completed"];

export const STAGE_LABELS: Record<StageName, string> = {
  idea: "Ý tưởng",
  lean_canvas: "Lean Canvas",
  bmc: "Mô hình kinh doanh",
  swot: "SWOT",
  product_plan: "Kế hoạch sản phẩm",
  marketing: "Tiếp thị",
  funding: "Gọi vốn",
  completed: "Hoàn thành"
};

export function nextStageLabel(stage: StageName): string | null {
  if (stage === "completed") {
    return null;
  }
  const currentIndex = STAGES.indexOf(stage);
  const nextStage = currentIndex === STAGES.length - 1 ? "completed" : STAGES[currentIndex + 1];
  return STAGE_LABELS[nextStage];
}

export function priorStages(stage: StageName): StageName[] {
  if (stage === "idea") {
    return [];
  }
  if (stage === "completed") {
    return [...STAGES];
  }
  return STAGES.slice(0, STAGES.indexOf(stage));
}
