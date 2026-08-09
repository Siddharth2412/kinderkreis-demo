import { useState } from "react";
import { registerUser } from "../api.js";
import { validatePasswords } from "../utils/validate.js";

export default function SignupView({ onNeedsVerification, onGoToLogin }) {
  const [form, setForm] = useState({ name: "", email: "", password: "", confirm: "", role: "eltern" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const set = (field, value) => setForm((f) => ({ ...f, [field]: value }));

  async function handleSubmit(e) {
    e.preventDefault();
    const validationError = validatePasswords(form.password, form.confirm);
    if (validationError) { setError(validationError); return; }
    setError("");
    setLoading(true);
    try {
      await registerUser(form.name, form.email, form.password, form.role);
      onNeedsVerification(form.email);
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
          <span className="eyebrow">Konto erstellen</span>
          <h1>Registrieren</h1>
          <p>Erstellen Sie ein kostenloses Kinderkreis-Konto.</p>
        </div>

        {error && <div className="form-error">{error}</div>}

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="field">
            <label>Ich bin</label>
            <div className="role-toggle">
              <button type="button" className={`role-btn ${form.role === "eltern" ? "active" : ""}`} onClick={() => set("role", "eltern")}>
                Elternteil
              </button>
              <button type="button" className={`role-btn ${form.role === "tagespflege" ? "active" : ""}`} onClick={() => set("role", "tagespflege")}>
                Tagespflegeperson
              </button>
            </div>
          </div>

          <div className="field">
            <label>Name</label>
            <input type="text" value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="Ihr vollständiger Name" required autoComplete="name" />
          </div>

          <div className="field">
            <label>E-Mail-Adresse</label>
            <input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} placeholder="ihre@email.de" required autoComplete="email" />
          </div>

          <div className="field">
            <label>Passwort</label>
            <input type="password" value={form.password} onChange={(e) => set("password", e.target.value)} placeholder="Mindestens 8 Zeichen" required autoComplete="new-password" />
          </div>

          <div className="field">
            <label>Passwort bestätigen</label>
            <input type="password" value={form.confirm} onChange={(e) => set("confirm", e.target.value)} placeholder="Passwort wiederholen" required autoComplete="new-password" />
          </div>

          <div className="form-actions">
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? "Wird registriert…" : "Konto erstellen"}
            </button>
          </div>
        </form>

        <p className="auth-switch">
          Bereits ein Konto?{" "}
          <button className="link-btn" onClick={onGoToLogin}>Jetzt anmelden</button>
        </p>
      </div>
    </div>
  );
}
