import { useMemo, useState } from "react";

type PasswordFieldProps = {
  value: string;
  onChange: (value: string) => void;
  autoComplete: "current-password" | "new-password";
  showStrength?: boolean;
};

export function PasswordField({ value, onChange, autoComplete, showStrength = false }: PasswordFieldProps) {
  const [isVisible, setIsVisible] = useState(false);
  const strength = useMemo(() => passwordStrength(value), [value]);

  return (
    <div className="password-field">
      <div className="input-with-action">
        <input
          type={isVisible ? "text" : "password"}
          autoComplete={autoComplete}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          required
          minLength={8}
          aria-label="Password"
          aria-describedby={showStrength ? "password-guidance" : undefined}
        />
        <button
          type="button"
          className="password-toggle"
          onClick={() => setIsVisible((current) => !current)}
          aria-label={isVisible ? "Hide password" : "Show password"}
          aria-pressed={isVisible}
        >
          {isVisible ? "Hide" : "Show"}
        </button>
      </div>
      {showStrength ? (
        <div className="password-guidance" id="password-guidance">
          <div className="password-strength-row">
            <span>Password strength</span>
            <strong>{strength.label}</strong>
          </div>
          <div className="password-meter" aria-hidden="true">
            <span style={{ width: `${strength.percent}%` }} data-level={strength.level} />
          </div>
          <p className={value.length >= 8 ? "requirement-met" : undefined}>
            <span aria-hidden="true">{value.length >= 8 ? "✓" : "○"}</span> At least 8 characters
          </p>
        </div>
      ) : null}
    </div>
  );
}

function passwordStrength(value: string) {
  if (!value) {
    return { label: "Empty", percent: 0, level: "empty" };
  }
  let score = value.length >= 8 ? 1 : 0;
  score += /[a-z]/.test(value) && /[A-Z]/.test(value) ? 1 : 0;
  score += /\d/.test(value) ? 1 : 0;
  score += /[^A-Za-z0-9]/.test(value) || value.length >= 12 ? 1 : 0;

  if (score <= 1) return { label: "Weak", percent: 25, level: "weak" };
  if (score === 2) return { label: "Medium", percent: 55, level: "medium" };
  if (score === 3) return { label: "Good", percent: 78, level: "good" };
  return { label: "Strong", percent: 100, level: "strong" };
}
