import { useEffect, useState } from "react";
import {
  fetchAdminProviders,
  fetchAdminCertificateBlob,
  verifyProviderCertificate,
  unverifyProviderCertificate,
} from "../api.js";
import AdminManageView from "./AdminManageView.jsx";

function formatTimestamp(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("de-DE");
}

// Admin review queue: every provider profile that has an uploaded
// Qualifikationsnachweis, newest upload first. Verifying here is the only
// way a provider gets the "✓ Geprüft" tick shown to parents on the public
// directory (see ProviderCard.jsx / ProviderDetailModal.jsx).
export default function AdminPanelView({ admin, onLogout }) {
  // "Admins verwalten" only ever exists for the super admin — a regular
  // admin's token 403s on every /api/admin/admins... endpoint anyway, but
  // there's no reason to even render the tab for them.
  const [tab, setTab] = useState("certificates");
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);

  function load() {
    setLoading(true);
    setError(null);
    fetchAdminProviders(admin.token)
      .then((data) => setProviders(data.providers))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(load, [admin.token]);

  async function handleView(providerId) {
    setError(null);
    try {
      const { blob, filename } = await fetchAdminCertificateBlob(admin.token, providerId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleToggleVerified(provider) {
    setBusyId(provider.id);
    setError(null);
    try {
      if (provider.certificate_verified) {
        await unverifyProviderCertificate(admin.token, provider.id);
      } else {
        await verifyProviderCertificate(admin.token, provider.id);
      }
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <div className="section-head admin-head">
        <div>
          <span className="eyebrow">Admin</span>
          <h1>{tab === "certificates" ? "Zertifikatsprüfung" : "Admins verwalten"}</h1>
          <p>
            {tab === "certificates"
              ? "Hochgeladene Qualifikationsnachweise ansehen und bestätigen."
              : "Admin-Konten anlegen sowie Passwort oder 2FA zurücksetzen."}
          </p>
        </div>
        <div className="admin-head-actions">
          <span className="nav-user-name">{admin.username}</span>
          <button className="btn-ghost btn-small" onClick={onLogout}>
            Abmelden
          </button>
        </div>
      </div>

      {admin.is_super_admin && (
        <div className="form-actions">
          <button
            className={tab === "certificates" ? "btn-primary btn-small" : "btn-ghost btn-small"}
            onClick={() => setTab("certificates")}
          >
            Zertifikate
          </button>
          <button
            className={tab === "admins" ? "btn-primary btn-small" : "btn-ghost btn-small"}
            onClick={() => setTab("admins")}
          >
            Admins verwalten
          </button>
        </div>
      )}

      {tab === "admins" ? (
        <AdminManageView token={admin.token} />
      ) : (
        <>
          {error && <div className="form-error">{error}</div>}

          {loading ? (
            <p className="result-count">Wird geladen …</p>
          ) : providers.length === 0 ? (
            <div className="empty-state">Noch keine hochgeladenen Zertifikate.</div>
          ) : (
            <div className="booking-list">
              {providers.map((p) => (
                <div className="booking-card" key={p.id}>
                  <div className="booking-card-head">
                    <div>
                      <div className="provider-name">{p.name}</div>
                      <div className="provider-city">
                        {p.city} · {p.owner_email}
                      </div>
                    </div>
                    {p.certificate_verified ? (
                      <span className="badge verified">✓ Geprüft</span>
                    ) : (
                      <span className="badge muted">Ausstehend</span>
                    )}
                  </div>
                  <p className="booking-meta">
                    📄 {p.certificate_original_name} · hochgeladen {formatTimestamp(p.certificate_uploaded_at)}
                    {p.certificate_verified_at && ` · geprüft ${formatTimestamp(p.certificate_verified_at)}`}
                  </p>
                  <div className="form-actions">
                    <button className="btn-ghost btn-small" onClick={() => handleView(p.id)}>
                      Zertifikat ansehen
                    </button>
                    <button
                      className="btn-primary btn-small"
                      disabled={busyId === p.id}
                      onClick={() => handleToggleVerified(p)}
                    >
                      {busyId === p.id
                        ? "…"
                        : p.certificate_verified
                        ? "Prüfung zurückziehen"
                        : "Als geprüft bestätigen"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
