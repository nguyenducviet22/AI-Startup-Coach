import { create } from "zustand";

export type ToastTone = "success" | "error" | "info";

type ToastMessage = {
  id: number;
  message: string;
  tone: ToastTone;
};

type ToastState = {
  toast: ToastMessage | null;
  showToast: (message: string, tone?: ToastTone) => void;
  dismissToast: (id?: number) => void;
};

export const useToastStore = create<ToastState>((set, get) => ({
  toast: null,
  showToast(message, tone = "info") {
    set({ toast: { id: Date.now(), message, tone } });
  },
  dismissToast(id) {
    if (id !== undefined && get().toast?.id !== id) {
      return;
    }
    set({ toast: null });
  }
}));
