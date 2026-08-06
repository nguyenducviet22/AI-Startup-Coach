import type { DocumentType } from "../../api/documents";
import type { StageName } from "../../api/startups";

export const DOCUMENT_TYPES: DocumentType[] = [
  "lean_canvas",
  "bmc",
  "swot",
  "product_plan",
  "marketing",
  "funding"
];

export const DOCUMENT_LABELS: Record<DocumentType, string> = {
  lean_canvas: "Lean Canvas",
  bmc: "Business Model Canvas",
  swot: "SWOT",
  product_plan: "Product Plan",
  marketing: "Marketing Plan",
  funding: "Funding Plan"
};

export function stageToDocumentType(stage: StageName): DocumentType | null {
  if (stage === "idea" || stage === "completed") {
    return null;
  }
  return stage;
}
