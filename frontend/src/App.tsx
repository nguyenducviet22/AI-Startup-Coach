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
    page = <main className="app-loading" aria-label="Đang mở không gian làm việc"><Skeleton lines={4} /></main>;
  } else if (profileQuery.error) {
    page = (
      <main className="app-error-state">
        <h1>Chưa thể mở AI Startup Coach</h1>
        <p>{profileQuery.error.message}</p>
        <button type="button" className="primary-button" onClick={() => void profileQuery.refetch()}>Thử lại</button>
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
        <p className="eyebrow">Chào mừng bạn</p>
        <h1 id="onboarding-title">Mình nên gọi bạn là gì?</h1>
        <p>Coach sẽ dùng tên này để đồng hành cùng bạn trong suốt hành trình xây dựng startup.</p>
        <form onSubmit={submit} className="onboarding-form">
          <label htmlFor="profile-name">Tên của bạn</label>
          <input id="profile-name" value={name} onChange={(event) => setName(event.target.value)} maxLength={255} autoFocus placeholder="Ví dụ: Nguyễn Thị Nhã Uyên" />
          {mutation.error ? <p className="form-error">{mutation.error.message}</p> : null}
          <button type="submit" className="primary-button" disabled={!name.trim() || mutation.isPending}>
            {mutation.isPending ? "Đang lưu..." : "Bắt đầu hành trình"}
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
