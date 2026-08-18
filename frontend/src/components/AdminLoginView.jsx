import { useState } from "react";
import { adminLogin } from "../api.js";

// Deliberately not the eltern/tagespflege login: separate username/password
// form. Reached only via the footer "Admin" link, never the main nav — see
// App.jsx. Step 1 only — a correct username/password never signs you in by
// itself, it hands back a pending-2FA ticket that App.jsx routes into
// AdminTwoFactorView (mandatory for every admin, no exceptions).
export default function AdminLoginView({ onLogin }) {
  const [form, setForm] = useState({ username: "", password: "" });
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
      const result = await adminLogin(form.username, form.password);
      onLogin(result);
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
          <h1>Admin-Anmeldung</h1>
          <p>Hochgeladene Zertifikate von Tagespflegepersonen prüfen und bestätigen.</p>
        </div>

        {error && <div className="form-error">{error}</div>}

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="field">
            <label>Benutzername</label>
            <input
              type="text"
              value={form.username}
              onChange={(e) => set("username", e.target.value)}
              required
              autoComplete="username"
              autoFocus
            />
          </div>

          <div className="field">
            <label>Passwort</label>
            <input
              type="password"
              value={form.password}
              onChange={(e) => set("password", e.target.value)}
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
      </div>
    </div>
  );
}
