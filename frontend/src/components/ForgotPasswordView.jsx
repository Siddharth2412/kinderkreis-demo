import { useState } from "react";
import { forgotPassword, resetPassword } from "../api.js";
import { validatePasswords } from "../utils/validate.js";

export default function ForgotPasswordView({ onGoToLogin }) {
  const [step, setStep] = useState("email"); // "email" | "otp"
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  async function handleSendOtp(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await forgotPassword(email);
      setStep("otp");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleReset(e) {
    e.preventDefault();
    const validationError = validatePasswords(newPassword, confirm);
    if (validationError) { setError(validationError); return; }
    setError("");
    setLoading(true);
    try {
      await resetPassword(email, otp, newPassword);
      setSuccess(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  if (success) {
    return (
      <div className="auth-wrap">
        <div className="auth-card">
          <div className="section-head">
            <span className="eyebrow">Erledigt</span>
            <h1>Passwort geändert</h1>
            <p>Ihr Passwort wurde erfolgreich zurückgesetzt. Sie können sich jetzt anmelden.</p>
          </div>
          <div className="form-actions">
            <button className="btn-primary" onClick={onGoToLogin}>Zur Anmeldung</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="section-head">
          <span className="eyebrow">Passwort zurücksetzen</span>
          <h1>{step === "email" ? "E-Mail eingeben" : "Code & neues Passwort"}</h1>
          <p>
            {step === "email"
              ? "Wir senden Ihnen einen Einmalcode an Ihre E-Mail-Adresse."
              : `Wir haben einen 6-stelligen Code an ${email} gesendet.`}
          </p>
        </div>

        {error && <div className="form-error">{error}</div>}

        {step === "email" ? (
          <form onSubmit={handleSendOtp} className="auth-form">
            <div className="field">
              <label>E-Mail-Adresse</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="ihre@email.de" required autoComplete="email" />
            </div>
            <div className="form-actions">
              <button type="submit" className="btn-primary" disabled={loading}>
                {loading ? "Wird gesendet…" : "Code senden"}
              </button>
            </div>
          </form>
        ) : (
          <form onSubmit={handleReset} className="auth-form">
            <div className="field">
              <label>Einmalcode (OTP)</label>
              <input
                type="text"
                inputMode="numeric"
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
                placeholder="6-stelliger Code"
                maxLength={6}
                required
                className="otp-input"
              />
            </div>
            <div className="field">
              <label>Neues Passwort</label>
              <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="Mindestens 8 Zeichen" required autoComplete="new-password" />
            </div>
            <div className="field">
              <label>Passwort bestätigen</label>
              <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder="Passwort wiederholen" required autoComplete="new-password" />
            </div>
            <div className="form-actions">
              <button type="submit" className="btn-primary" disabled={loading}>
                {loading ? "Wird gespeichert…" : "Passwort ändern"}
              </button>
              <button type="button" className="btn-ghost" onClick={() => setStep("email")}>
                Code erneut senden
              </button>
            </div>
          </form>
        )}

        <p className="auth-switch">
          <button className="link-btn" onClick={onGoToLogin}>Zurück zur Anmeldung</button>
        </p>
      </div>
    </div>
  );
}
