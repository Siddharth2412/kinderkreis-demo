import { useState } from "react";
import { verifyEmail, resendVerification } from "../api.js";

export default function VerifyEmailView({ email, onVerified }) {
  const [otp, setOtp] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);

  async function handleVerify(e) {
    e.preventDefault();
    setError("");
    setInfo("");
    setLoading(true);
    try {
      const user = await verifyEmail(email, otp);
      onVerified(user);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleResend() {
    setError("");
    setInfo("");
    setResending(true);
    try {
      await resendVerification(email);
      setInfo("Ein neuer Code wurde gesendet.");
    } catch (err) {
      setError(err.message);
    } finally {
      setResending(false);
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="section-head">
          <span className="eyebrow">Fast geschafft</span>
          <h1>E-Mail bestätigen</h1>
          <p>
            Wir haben einen 6-stelligen Bestätigungscode an <strong>{email}</strong> gesendet.
            Bitte prüfen Sie Ihr Postfach und geben Sie den Code ein.
          </p>
        </div>

        {error && <div className="form-error">{error}</div>}
        {info && <div className="form-success">{info}</div>}

        <form onSubmit={handleVerify} className="auth-form">
          <div className="field">
            <label>Bestätigungscode</label>
            <input
              type="text"
              inputMode="numeric"
              value={otp}
              onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
              placeholder="6-stelliger Code"
              maxLength={6}
              required
              autoComplete="one-time-code"
              className="otp-input"
            />
          </div>

          <div className="form-actions">
            <button type="submit" className="btn-primary" disabled={loading || otp.length < 6}>
              {loading ? "Wird geprüft…" : "Bestätigen"}
            </button>
          </div>
        </form>

        <p className="auth-switch">
          Keinen Code erhalten?{" "}
          <button className="link-btn" onClick={handleResend} disabled={resending}>
            {resending ? "Wird gesendet…" : "Erneut senden"}
          </button>
        </p>
      </div>
    </div>
  );
}
