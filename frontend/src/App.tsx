import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { getLocalProfile, updateLocalProfile } from "./api/profile";
import { AppShell } from "./components/AppShell";
import { Skeleton } from "./components/Skeleton";
import { ToastViewport } from "./components/ToastViewport";

export function App() {
  const profileQuery = useQuery({ queryKey: ["profile"], queryFn: getLocalProfile, retry: false });

  let page: React.ReactNode;
  if (profileQuery.isLoading) {
    page = <main className="app-loading" aria-label="Opening workspace"><Skeleton lines={4} /></main>;
  } else if (profileQuery.error) {
    page = (
      <main className="app-error-state">
        <h1>Unable to open AI Startup Coach</h1>
        <p>{profileQuery.error.message}</p>
        <button type="button" className="primary-button" onClick={() => void profileQuery.refetch()}>Try again</button>
      </main>
    );
  } else if (!profileQuery.data?.configured) {
    page = <ProfileOnboarding />;
  } else {
    page = <AppShell profileName={profileQuery.data.name} />;
  }

  return <>{page}<ToastViewport /></>;
}

function ProfileOnboarding() {
  const [name, setName] = useState("");
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: updateLocalProfile,
    onSuccess(profile) {
      queryClient.setQueryData(["profile"], profile);
    }
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedName = name.trim();
    if (trimmedName) mutation.mutate(trimmedName);
  }

  return (
    <main className="onboarding-page">
      <section className="onboarding-card" aria-labelledby="onboarding-title">
        <p className="tool-name">AI Startup Coach</p>
        <p className="eyebrow">Welcome</p>
        <h1 id="onboarding-title">What should I call you?</h1>
        <p>Your coach will use this name throughout your startup-building journey.</p>
        <form onSubmit={submit} className="onboarding-form">
          <label htmlFor="profile-name">Your name</label>
          <input id="profile-name" value={name} onChange={(event) => setName(event.target.value)} maxLength={255} autoFocus placeholder="e.g. Alex Johnson" />
          {mutation.error ? <p className="form-error">{mutation.error.message}</p> : null}
          <button type="submit" className="primary-button" disabled={!name.trim() || mutation.isPending}>
            {mutation.isPending ? "Saving..." : "Start journey"}
          </button>
        </form>
      </section>
    </main>
  );
}

// Legacy auth pages remain source-compatible while the local runtime bypasses them.
export function AuthSwitchLink(_props: { mode: "login" | "signup" }) {
  return null;
}
