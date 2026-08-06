import { FormEvent, useState } from "react";

import { AuthSwitchLink } from "../App";
import { PasswordField } from "../components/PasswordField";
import { AuthPage } from "./LoginPage";
import { useAuthStore } from "../stores/authStore";
import { useToastStore } from "../stores/toastStore";

export function SignupPage() {
  const signup = useAuthStore((state) => state.signup);
  const error = useAuthStore((state) => state.error);
  const clearError = useAuthStore((state) => state.clearError);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const showToast = useToastStore((state) => state.showToast);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    clearError();
    try {
      await signup(name, email, password);
      showToast("Account created successfully. Start with your first idea!", "success");
    } catch {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthPage title="Create an account" subtitle="Start a guided journey from idea to fundraising plan.">
      <form className="auth-form" onSubmit={onSubmit}>
        <label>
          Full name
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
          <PasswordField value={password} onChange={setPassword} autoComplete="new-password" showStrength />
        </label>
        {error ? <p className="form-error">{error}</p> : null}
        <button type="submit" className="primary-button" disabled={isSubmitting}>
          {isSubmitting ? "Creating account..." : "Create account"}
        </button>
      </form>
      <AuthSwitchLink mode="signup" />
    </AuthPage>
  );
}
