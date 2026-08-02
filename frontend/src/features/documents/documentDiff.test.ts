import { describe, expect, it } from "vitest";

import { diffDocumentContent } from "./documentDiff";

describe("diffDocumentContent", () => {
  it("reports changed scalar fields and added/removed list items", () => {
    expect(diffDocumentContent(
      { problem: "Old problem", channels: ["Facebook", "Campus"] },
      { problem: "New problem", channels: ["Campus", "Clubs"] }
    )).toEqual([
      { field: "problem", kind: "changed", before: ["Old problem"], after: ["New problem"] },
      { field: "channels", kind: "list", before: ["Facebook", "Campus"], after: ["Campus", "Clubs"], added: ["Clubs"], removed: ["Facebook"] }
    ]);
  });

  it("omits fields whose normalized values are unchanged", () => {
    expect(diffDocumentContent({ strengths: ["Fast"] }, { strengths: ["Fast"] })).toEqual([]);
  });
});
