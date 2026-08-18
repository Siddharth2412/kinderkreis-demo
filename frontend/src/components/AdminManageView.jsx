import { useEffect, useState } from "react";
import { createAdmin, deactivateAdmin, fetchAdmins, resetAdminPassword, resetAdminTotp } from "../api.js";

function formatTimestamp(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("de-DE");
}

const CREATE_INITIAL = { username: "", password: "" };

// Super-admin-only panel: create/reset-password/reset-2FA/deactivate other
// admin accounts. Regular admins never see this (AdminPanelView only
// renders it when admin.is_super_admin) and the backend rejects every one
// of these endpoints with a 403 for a non-super-admin token regardless.
export default function AdminManageView({ token }) {
  const [admins, setAdmins] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyUsername, setBusyUsername] = useState(null);

  const [createForm, setCreateForm] = useState(CREATE_INITIAL);
  const [creating, setCreating] = useState(false);
  const [createdInfo, setCreatedInfo] = useState(null);

  // At most one inline action open at a time: {username, type: "reset-password" | "deactivate"}
  const [activeAction, setActiveAction] = useState(null);
  const [newPassword, setNewPassword] = useState("");

  function load() {
    setLoading(true);
    setError(null);
    fetchAdmins(token)
      .then((data) => setAdmins(data.admins))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(load, [token]);

  function closeAction() {
    setActiveAction(null);
    setNewPassword("");
  }

  async function handleCreate(e) {
    e.preventDefault();
    setError(null);
    setCreatedInfo(null);
    setCreating(true);
    try {
      await createAdmin(token, createForm.username, createForm.password);
      setCreatedInfo(
        `${createForm.username} wurde angelegt. Geben Sie das Passwort sicher weiter — beim ersten Anmelden ` +
          "richtet der Account seine eigene Zwei-Faktor-Authentifizierung ein."
      );
      setCreateForm(CREATE_INITIAL);
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  }

  async function handleResetPassword(username) {
    if (newPassword.length < 8) {
      setError("Das neue Passwort muss mindestens 8 Zeichen lang sein.");
      return;
    }
    setBusyUsername(username);
    setError(null);
    try {
      await resetAdminPassword(token, username, newPassword);
      closeAction();
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyUsername(null);
    }
  }

  async function handleResetTotp(username) {
    setBusyUsername(username);
    setError(null);
    try {
      await resetAdminTotp(token, username);
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyUsername(null);
    }
  }

  async function handleDeactivate(username) {
    setBusyUsername(username);
    setError(null);
    try {
      await deactivateAdmin(token, username);
      closeAction();
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyUsername(null);
    }
  }

  return (
    <div>
      <div className="section-head">
        <span className="eyebrow">Super-Admin</span>
        <h1>Admins verwalten</h1>
        <p>
          Neue Admin-Konten anlegen sowie Passwort oder 2FA zurücksetzen. Admins können ihren eigenen
          Benutzernamen/Passwort nicht selbst ändern — das läuft ausschließlich über dieses Panel.
        </p>
      </div>

      {error && <div className="form-error">{error}</div>}
      {createdInfo && <div className="form-success">{createdInfo}</div>}

      <form onSubmit={handleCreate} className="form-grid">
        <div className="field">
          <label htmlFor="new_admin_username">Neuer Benutzername</label>
          <input
            id="new_admin_username"
            required
            value={createForm.username}
            onChange={(e) => setCreateForm((f) => ({ ...f, username: e.target.value }))}
          />
        </div>
        <div className="field">
          <label htmlFor="new_admin_password">Initiales Passwort</label>
          <input
            id="new_admin_password"
            type="password"
            required
            minLength={8}
            value={createForm.password}
            onChange={(e) => setCreateForm((f) => ({ ...f, password: e.target.value }))}
          />
        </div>
        <div className="field span-2">
          <div className="form-actions">
            <button className="btn-primary btn-small" type="submit" disabled={creating}>
              {creating ? "Wird angelegt …" : "Admin anlegen"}
            </button>
          </div>
        </div>
      </form>

      {loading ? (
        <p className="result-count">Wird geladen …</p>
      ) : (
        <div className="booking-list">
          {admins.map((a) => {
            const isSuperAdmin = a.role === "super_admin";
            const busy = busyUsername === a.username;
            return (
              <div className="booking-card" key={a.username}>
                <div className="booking-card-head">
                  <div>
                    <div className="provider-name">{a.username}</div>
                    <div className="provider-city">angelegt {formatTimestamp(a.created_at)}</div>
                  </div>
                  {isSuperAdmin ? (
                    <span className="badge">Super-Admin</span>
                  ) : a.is_active ? (
                    <span className="badge verified">Aktiv</span>
                  ) : (
                    <span className="badge muted">Deaktiviert</span>
                  )}
                </div>
                <p className="booking-meta">
                  {a.totp_enrolled ? "✓ Zwei-Faktor-Authentifizierung eingerichtet" : "Noch nicht angemeldet / 2FA ausstehend"}
                </p>

                {!isSuperAdmin && activeAction?.username !== a.username && (
                  <div className="form-actions">
                    <button
                      className="btn-ghost btn-small"
                      disabled={busy}
                      onClick={() => setActiveAction({ username: a.username, type: "reset-password" })}
                    >
                      Passwort zurücksetzen
                    </button>
                    <button className="btn-ghost btn-small" disabled={busy} onClick={() => handleResetTotp(a.username)}>
                      {busy ? "…" : "2FA zurücksetzen"}
                    </button>
                    {a.is_active && (
                      <button
                        className="btn-ghost btn-small"
                        disabled={busy}
                        onClick={() => setActiveAction({ username: a.username, type: "deactivate" })}
                      >
                        Deaktivieren
                      </button>
                    )}
                  </div>
                )}

                {!isSuperAdmin && activeAction?.username === a.username && activeAction.type === "reset-password" && (
                  <div className="decline-reason-form">
                    <input
                      type="password"
                      className="decline-reason-input"
                      placeholder="Neues Passwort (mind. 8 Zeichen)"
                      minLength={8}
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      autoFocus
                    />
                    <div className="form-actions">
                      <button
                        className="btn-primary btn-small"
                        disabled={busy}
                        onClick={() => handleResetPassword(a.username)}
                      >
                        {busy ? "Wird gesetzt …" : "Neues Passwort setzen"}
                      </button>
                      <button className="btn-ghost btn-small" disabled={busy} onClick={closeAction}>
                        Abbrechen
                      </button>
                    </div>
                  </div>
                )}

                {!isSuperAdmin && activeAction?.username === a.username && activeAction.type === "deactivate" && (
                  <div className="decline-reason-form">
                    <p className="modal-bio">
                      {a.username} kann sich danach nicht mehr anmelden, und eine aktuell offene Sitzung wird
                      sofort beendet. Wirklich deaktivieren?
                    </p>
                    <div className="form-actions">
                      <button
                        className="btn-primary btn-small"
                        disabled={busy}
                        onClick={() => handleDeactivate(a.username)}
                      >
                        {busy ? "…" : "Ja, deaktivieren"}
                      </button>
                      <button className="btn-ghost btn-small" disabled={busy} onClick={closeAction}>
                        Abbrechen
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
