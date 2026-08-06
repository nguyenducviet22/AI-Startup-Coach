import { FormEvent, useEffect, useRef, useState } from "react";

import { getStoredOpenRouterApiKey, setStoredOpenRouterApiKey } from "../api/client";

export function OpenRouterKeyControl() {
  const [isOpen, setIsOpen] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [isVisible, setIsVisible] = useState(false);
  const [hasApiKey, setHasApiKey] = useState(() => Boolean(getStoredOpenRouterApiKey()));
  const dialogRef = useRef<HTMLElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    inputRef.current?.focus();
    return () => previouslyFocused?.focus();
  }, [isOpen]);

  function openDialog() {
    setApiKey(getStoredOpenRouterApiKey() ?? "");
    setIsVisible(false);
    setIsOpen(true);
  }

  function closeDialog() {
    setApiKey("");
    setIsVisible(false);
    setIsOpen(false);
  }

  function saveApiKey(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedApiKey = apiKey.trim();
    if (!trimmedApiKey) return;
    setStoredOpenRouterApiKey(trimmedApiKey);
    setHasApiKey(true);
    closeDialog();
  }

  function removeApiKey() {
    setStoredOpenRouterApiKey(null);
    setHasApiKey(false);
    closeDialog();
  }

  return (
    <>
      <button
        type="button"
        className={hasApiKey ? "api-key-button configured" : "api-key-button"}
        onClick={openDialog}
        aria-label={hasApiKey ? "OpenRouter API key configured" : "Add OpenRouter API key"}
      >
        <KeyIcon />
        <span>API key</span>
        {hasApiKey ? <i aria-hidden="true" /> : null}
      </button>

      {isOpen ? (
        <div className="dialog-backdrop" onMouseDown={(event) => event.target === event.currentTarget && closeDialog()}>
          <section
            ref={dialogRef}
            className="confirmation-dialog api-key-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="api-key-dialog-title"
            aria-describedby="api-key-dialog-description"
            onKeyDown={(event) => trapDialogKeyboard(event, dialogRef.current, closeDialog)}
          >
            <div className="dialog-icon api-key-dialog-icon" aria-hidden="true"><KeyIcon /></div>
            <h2 id="api-key-dialog-title">Connect OpenRouter</h2>
            <p id="api-key-dialog-description">
              Enter <code>OPENROUTER_API_KEY</code> for AI Coach to use OpenRouter in this session.
            </p>
            <form className="api-key-form" onSubmit={saveApiKey}>
              <label htmlFor="openrouter-api-key">OpenRouter API key</label>
              <div className="input-with-action">
                <input
                  ref={inputRef}
                  id="openrouter-api-key"
                  type={isVisible ? "text" : "password"}
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  autoComplete="off"
                  spellCheck={false}
                  placeholder="sk-or-v1-..."
                  required
                />
                <button
                  type="button"
                  className="password-toggle"
                  onClick={() => setIsVisible((current) => !current)}
                  aria-label={isVisible ? "Hide API key" : "Show API key"}
                  aria-pressed={isVisible}
                >
                  {isVisible ? "Hide" : "Show"}
                </button>
              </div>
              <p className="api-key-privacy">The key is stored only in this browser tab and is sent to the backend only when you message AI Coach.</p>
              <div className="dialog-actions api-key-dialog-actions">
                {hasApiKey ? <button type="button" className="danger-text-button" onClick={removeApiKey}>Remove key</button> : null}
                <span />
                <button type="button" className="secondary-button" onClick={closeDialog}>Cancel</button>
                <button type="submit" className="primary-button" disabled={!apiKey.trim()}>Save key</button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </>
  );
}

function KeyIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">
      <circle cx="8" cy="15" r="4" fill="none" stroke="currentColor" strokeWidth="2" />
      <path d="m11 12 8-8m-2 2 2 2m-5 1 2 2" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function trapDialogKeyboard(
  event: React.KeyboardEvent<HTMLElement>,
  dialog: HTMLElement | null,
  closeDialog: () => void
) {
  if (event.key === "Escape") {
    closeDialog();
    return;
  }
  if (event.key !== "Tab") return;
  const controls = dialog?.querySelectorAll<HTMLElement>("input, button:not(:disabled)");
  if (!controls?.length) return;
  const first = controls[0];
  const last = controls[controls.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}
