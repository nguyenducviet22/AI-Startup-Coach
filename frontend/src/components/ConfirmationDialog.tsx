import { useEffect, useRef } from "react";

type ConfirmationDialogProps = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmationDialog({
  open,
  title,
  description,
  confirmLabel,
  cancelLabel = "Cancel",
  onConfirm,
  onCancel
}: ConfirmationDialogProps) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    const previouslyFocused = document.activeElement as HTMLElement | null;
    cancelRef.current?.focus();
    return () => previouslyFocused?.focus();
  }, [open]);

  if (!open) {
    return null;
  }

  return (
    <div className="dialog-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onCancel()}>
      <section
        ref={dialogRef}
        className="confirmation-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirmation-title"
        aria-describedby="confirmation-description"
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            onCancel();
            return;
          }
          if (event.key !== "Tab") {
            return;
          }
          const controls = dialogRef.current?.querySelectorAll<HTMLElement>("button:not(:disabled)");
          if (!controls?.length) {
            return;
          }
          const first = controls[0];
          const last = controls[controls.length - 1];
          if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
          } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
          }
        }}
      >
        <div className="dialog-icon" aria-hidden="true">?</div>
        <h2 id="confirmation-title">{title}</h2>
        <p id="confirmation-description">{description}</p>
        <div className="dialog-actions">
          <button type="button" className="secondary-button" onClick={onCancel} ref={cancelRef}>
            {cancelLabel}
          </button>
          <button type="button" className="primary-button" onClick={onConfirm}>
            {confirmLabel}
          </button>
        </div>
      </section>
    </div>
  );
}
