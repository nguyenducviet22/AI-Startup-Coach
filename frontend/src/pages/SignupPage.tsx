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
      showToast("Tạo tài khoản thành công. Hãy bắt đầu với ý tưởng đầu tiên!", "success");
    } catch {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthPage title="Tạo tài khoản" subtitle="Bắt đầu hành trình có hướng dẫn từ ý tưởng đến kế hoạch gọi vốn.">
      <form className="auth-form" onSubmit={onSubmit}>
        <label>
          Họ và tên
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
          Mật khẩu
          <PasswordField value={password} onChange={setPassword} autoComplete="new-password" showStrength />
        </label>
        {error ? <p className="form-error">{error}</p> : null}
        <button type="submit" className="primary-button" disabled={isSubmitting}>
          {isSubmitting ? "Đang tạo tài khoản..." : "Tạo tài khoản"}
        </button>
      </form>
      <AuthSwitchLink mode="signup" />
    </AuthPage>
  );
}
