import { useEffect } from "react";

import { useToastStore } from "../stores/toastStore";

export function ToastViewport() {
  const toast = useToastStore((state) => state.toast);
  const dismissToast = useToastStore((state) => state.dismissToast);

  useEffect(() => {
    if (!toast) {
      return;
    }
    const timer = window.setTimeout(() => dismissToast(toast.id), 4200);
    return () => window.clearTimeout(timer);
  }, [dismissToast, toast]);

  if (!toast) {
    return null;
  }

  return (
    <div className="toast-viewport" aria-live={toast.tone === "error" ? "assertive" : "polite"}>
      <div className={`toast toast-${toast.tone}`} role={toast.tone === "error" ? "alert" : "status"}>
        <span className="toast-indicator" aria-hidden="true" />
        <p>{toast.message}</p>
        <button type="button" className="icon-button" onClick={() => dismissToast(toast.id)} aria-label="Đóng thông báo">
          ×
        </button>
      </div>
    </div>
  );
}
