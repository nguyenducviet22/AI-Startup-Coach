import { apiRequest } from "./client";

export type StageName =
  | "idea"
  | "lean_canvas"
  | "bmc"
  | "swot"
  | "product_plan"
  | "marketing"
  | "funding"
  | "completed";

export type Startup = {
  id: string;
  user_id: string;
  name: string | null;
  current_stage: StageName;
  created_at: string | null;
  updated_at: string | null;
};

export type StartupListResponse = {
  startups: Startup[];
};

export async function listStartups(): Promise<StartupListResponse> {
  return apiRequest<StartupListResponse>("/startups");
}

export async function createStartup(name: string | null): Promise<Startup> {
  return apiRequest<Startup>("/startups", {
    method: "POST",
    body: JSON.stringify({ name })
  });
}

export async function renameStartup(startupId: string, name: string): Promise<Startup> {
  return apiRequest<Startup>(`/startups/${startupId}`, {
    method: "PATCH",
    body: JSON.stringify({ name })
  });
}

export async function advanceStartupStage(startupId: string): Promise<Startup> {
  return apiRequest<Startup>(`/startups/${startupId}/advance-stage`, {
    method: "POST"
  });
}

export async function setStartupStage(startupId: string, stage: StageName): Promise<Startup> {
  return apiRequest<Startup>(`/startups/${startupId}/stage`, {
    method: "PATCH",
    body: JSON.stringify({ stage })
  });
}
