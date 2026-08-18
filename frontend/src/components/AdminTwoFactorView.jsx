import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { adminVerifyTwoFactor } from "../api.js";

// Step 2 of admin login (see AdminLoginView.jsx for step 1). `pending` is
// whatever POST /api/admin/login returned: always {ticket}, plus either
// {mode: "verify"} for an already-enrolled admin, or {mode: "enroll",
// otpauth_uri, secret} the very first time — 2FA is mandatory for every
// admin, so every admin passes through this view on every login.
export default function AdminTwoFactorView({ pending, onVerified, onCancel }) {
  const [qrDataUrl, setQrDataUrl] = useState(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const isEnroll = pending.mode === "enroll";

  useEffect(() => {
    if (!isEnroll) return;
    let cancelled = false;
    QRCode.toDataURL(pending.otpauth_uri)
      .then((url) => {
        if (!cancelled) setQrDataUrl(url);
      })
      .catch(() => {
        // QR rendering failing (e.g. an unexpected otpauth_uri) still
        // leaves the manual-entry secret below as a working fallback.
      });
    return () => {
      cancelled = true;
    };
  }, [isEnroll, pending.otpauth_uri]);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await adminVerifyTwoFactor(pending.ticket, code);
      onVerified(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="section-head">
          <span className="eyebrow">Admin</span>
          <h1>{isEnroll ? "Zwei-Faktor-Authentifizierung einrichten" : "Anmeldecode eingeben"}</h1>
          {isEnroll ? (
            <p>
              Scannen Sie diesen QR-Code mit einer Authenticator-App (z. B. Google Authenticator, Authy oder
              1Password) und geben Sie anschließend den angezeigten 6-stelligen Code ein, um die Einrichtung
              abzuschließen.
            </p>
          ) : (
            <p>Geben Sie den 6-stelligen Code aus Ihrer Authenticator-App ein.</p>
          )}
        </div>

        {error && <div className="form-error">{error}</div>}

        {isEnroll && (
          <>
            {qrDataUrl && <img className="totp-qr" src={qrDataUrl} alt="QR-Code für die Authenticator-App" />}
            <p className="form-hint">Kann der Code nicht gescannt werden? Manuell eingeben:</p>
            <div className="totp-secret">{pending.secret}</div>
          </>
        )}

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="field">
            <label>Code</label>
            <input
              type="text"
              inputMode="numeric"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              placeholder="6-stelliger Code"
              maxLength={6}
              required
              autoComplete="one-time-code"
              autoFocus
              className="otp-input"
            />
          </div>

          <div className="form-actions">
            <button type="submit" className="btn-primary" disabled={loading || code.length < 6}>
              {loading ? "Wird geprüft…" : isEnroll ? "Einrichtung abschließen" : "Anmelden"}
            </button>
            {onCancel && (
              <button type="button" className="btn-ghost" onClick={onCancel}>
                Abbrechen
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
