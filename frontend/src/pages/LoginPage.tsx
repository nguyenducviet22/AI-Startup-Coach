import { FormEvent, useState } from "react";

import { AuthSwitchLink } from "../App";
import { PasswordField } from "../components/PasswordField";
import { useAuthStore } from "../stores/authStore";
import { useToastStore } from "../stores/toastStore";

export function LoginPage() {
  const login = useAuthStore((state) => state.login);
  const error = useAuthStore((state) => state.error);
  const clearError = useAuthStore((state) => state.clearError);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const showToast = useToastStore((state) => state.showToast);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    clearError();
    try {
      await login(email, password);
      showToast("Login successful. Welcome back!", "success");
    } catch {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthPage title="Welcome back" subtitle="Log in to continue building your startup.">
      <form className="auth-form" onSubmit={onSubmit}>
        <label>
          Email
          <input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </label>
        <label>
          Password
          <PasswordField value={password} onChange={setPassword} autoComplete="current-password" />
        </label>
        {error ? <p className="form-error">{error}</p> : null}
        <button type="submit" className="primary-button" disabled={isSubmitting}>
          {isSubmitting ? "Logging in..." : "Log in"}
        </button>
      </form>
      <AuthSwitchLink mode="login" />
    </AuthPage>
  );
}

export function AuthPage({
  title,
  subtitle,
  children
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <main className="auth-page">
      <section className="auth-shell" aria-labelledby="auth-title">
        <div className="auth-brand-panel" aria-hidden="true">
          <div className="brand-lockup brand-lockup-inverse">
            <div className="brand-mark">DL</div>
            <strong>AI Startup Coach</strong>
          </div>
          <div className="auth-brand-message">
            <p className="eyebrow">From idea to plan</p>
            <h2>Build your startup step by step with an always-ready partner.</h2>
            <p>Explore problems, validate your model, and complete your documents in one focused workspace.</p>
          </div>
          <div className="journey-preview">
            <span>01 · Idea</span><span>02 · Model</span><span>03 · Product</span><span>04 · Funding</span>
          </div>
        </div>
        <div className="auth-form-panel">
          <div className="auth-mobile-brand">
            <div className="brand-mark" aria-hidden="true">DL</div>
            <strong>AI Startup Coach</strong>
          </div>
          <div className="auth-form-content">
            <p className="eyebrow">AI Startup Coach</p>
            <h1 id="auth-title">{title}</h1>
            <p className="auth-subtitle">{subtitle}</p>
            {children}
          </div>
        </div>
      </section>
    </main>
  );
}
