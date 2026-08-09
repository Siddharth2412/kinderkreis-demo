import { useState } from "react";
import { loginUser } from "../api.js";

export default function LoginView({ onLogin, onGoToSignup, onGoToForgot }) {
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const user = await loginUser(form.email, form.password);
      onLogin(user);
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
          <span className="eyebrow">Willkommen zurück</span>
          <h1>Anmelden</h1>
          <p>Melden Sie sich an, um auf Ihr Kinderkreis-Konto zuzugreifen.</p>
        </div>

        {error && <div className="form-error">{error}</div>}

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="field">
            <label>E-Mail-Adresse</label>
            <input
              type="email"
              value={form.email}
              onChange={(e) => set("email", e.target.value)}
              placeholder="ihre@email.de"
              required
              autoComplete="email"
            />
          </div>

          <div className="field">
            <label>Passwort</label>
            <input
              type="password"
              value={form.password}
              onChange={(e) => set("password", e.target.value)}
              placeholder="Mindestens 8 Zeichen"
              required
              autoComplete="current-password"
            />
          </div>

          <div className="form-actions">
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? "Wird angemeldet…" : "Anmelden"}
            </button>
          </div>
        </form>

        <p className="auth-switch">
          <button className="link-btn" onClick={onGoToForgot}>
            Passwort vergessen?
          </button>
        </p>
        <p className="auth-switch">
          Noch kein Konto?{" "}
          <button className="link-btn" onClick={onGoToSignup}>
            Jetzt registrieren
          </button>
        </p>
      </div>
    </div>
  );
}
