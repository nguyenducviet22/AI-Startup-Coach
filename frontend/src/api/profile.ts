import { apiRequest } from "./client";

export type LocalProfile = {
  name: string;
  configured: boolean;
};

export function getLocalProfile(): Promise<LocalProfile> {
  return apiRequest<LocalProfile>("/profile", { auth: false });
}
export function updateLocalProfile(name: string): Promise<LocalProfile> {
  return apiRequest<LocalProfile>("/profile", {
    method: "PUT",
    auth: false,
    body: JSON.stringify({ name })
  });
}
