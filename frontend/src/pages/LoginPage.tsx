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
      showToast("Đăng nhập thành công. Chào mừng bạn quay lại!", "success");
    } catch {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthPage title="Chào mừng trở lại" subtitle="Đăng nhập để tiếp tục hành trình xây dựng startup của bạn.">
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
          Mật khẩu
          <PasswordField value={password} onChange={setPassword} autoComplete="current-password" />
        </label>
        {error ? <p className="form-error">{error}</p> : null}
        <button type="submit" className="primary-button" disabled={isSubmitting}>
          {isSubmitting ? "Đang đăng nhập..." : "Đăng nhập"}
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
            <p className="eyebrow">Từ ý tưởng đến kế hoạch</p>
            <h2>Xây startup từng bước, với một người đồng hành luôn sẵn sàng.</h2>
            <p>Khám phá vấn đề, kiểm chứng mô hình và hoàn thiện tài liệu trong một không gian làm việc rõ ràng.</p>
          </div>
          <div className="journey-preview">
            <span>01 · Ý tưởng</span><span>02 · Mô hình</span><span>03 · Sản phẩm</span><span>04 · Gọi vốn</span>
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
