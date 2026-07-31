import { describe, expect, it } from "vitest";

import { priorStages, STAGES } from "./stageLabels";

describe("priorStages", () => {
  it("returns no go-back targets for the first stage", () => {
    expect(priorStages("idea")).toEqual([]);
  });

  it("returns every coaching stage as a go-back target from completed", () => {
    expect(priorStages("completed")).toEqual(STAGES);
  });

  it("returns only stages strictly before the current coaching stage", () => {
    expect(priorStages("product_plan")).toEqual(["idea", "lean_canvas", "bmc", "swot"]);
  });
});
