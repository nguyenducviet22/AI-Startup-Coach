import { FormEvent, useState } from "react";

import { AuthSwitchLink } from "../App";
import { AuthPage } from "./LoginPage";
import { useAuthStore } from "../stores/authStore";

export function SignupPage() {
  const signup = useAuthStore((state) => state.signup);
  const error = useAuthStore((state) => state.error);
  const clearError = useAuthStore((state) => state.clearError);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    clearError();
    try {
      await signup(name, email, password);
    } catch {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthPage title="Create your account" subtitle="Start a guided path from idea to funding plan.">
      <form className="auth-form" onSubmit={onSubmit}>
        <label>
          Name
          <input
            type="text"
            autoComplete="name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
          />
        </label>
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
          <input
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            minLength={8}
          />
        </label>
        {error ? <p className="form-error">{error}</p> : null}
        <button type="submit" className="primary-button" disabled={isSubmitting}>
          {isSubmitting ? "Creating..." : "Create account"}
        </button>
      </form>
      <AuthSwitchLink mode="signup" />
    </AuthPage>
  );
}
