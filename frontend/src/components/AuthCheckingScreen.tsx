export function AuthCheckingScreen() {
  return (
    <main className="auth-check" aria-busy="true">
      <div className="brand-lockup">
        <div className="brand-mark" aria-hidden="true">DL</div>
        <strong>AI Startup Coach</strong>
      </div>
      <div className="auth-check-loader" aria-hidden="true" />
      <p>Đang kiểm tra phiên đăng nhập...</p>
    </main>
  );
}
