import { useEffect, useRef, useState } from "react";
import {
  fetchMyProvider,
  createMyProvider,
  updateMyProvider,
  uploadMyCertificate,
  deleteMyCertificate,
  fetchMyCertificateBlob,
} from "../api.js";

const ALLOWED_CERTIFICATE_TYPES = ["application/pdf", "image/jpeg", "image/png"];
const MAX_CERTIFICATE_BYTES = 5 * 1024 * 1024; // matches the backend's CERTIFICATE_MAX_BYTES

const INITIAL = {
  name: "",
  city: "",
  min_age_months: 0,
  max_age_months: 36,
  care_type: "individual",
  staff_count: 1,
  capacity_total: 5,
  capacity_used: 0,
  qualification_hours: 300,
  practicum_hours: 80,
  has_pflegeerlaubnis: true,
  bio: "",
  phone: "",
  contact_email: "",
  website: "",
};

const MAX_CAPACITY = { individual: 5, group: 10 };

// Own profile page for a logged-in Tagespflegeperson: shows their current
// listing (prefilled into the form) if one exists, and lets them create or
// change it. Mapped to their account via the session token — never shown on
// the public "Für Eltern" directory.
export default function ProfileView({ token }) {
  const [form, setForm] = useState(INITIAL);
  const [mode, setMode] = useState(null); // "create" | "edit"
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const [hasCertificate, setHasCertificate] = useState(false);
  const [certificateVerified, setCertificateVerified] = useState(false);
  const [certBusy, setCertBusy] = useState(false);
  const [certError, setCertError] = useState(null);
  const [certSuccess, setCertSuccess] = useState(null);
  const certInputRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchMyProvider(token)
      .then(({ provider }) => {
        if (cancelled) return;
        if (provider) {
          const { is_certified, free_places, id, has_certificate, certificate_verified, ...editable } = provider;
          setForm(editable);
          setMode("edit");
          setHasCertificate(has_certificate);
          setCertificateVerified(certificate_verified);
        } else {
          setMode("create");
        }
      })
      .catch((err) => !cancelled && setError(err.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [token]);

  const update = (key, value) => {
    setForm((f) => {
      const next = { ...f, [key]: value };
      if (key === "care_type") {
        next.staff_count = value === "individual" ? 1 : 2;
        next.capacity_total = Math.min(next.capacity_total, MAX_CAPACITY[value]);
      }
      return next;
    });
  };

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (Number(form.max_age_months) < Number(form.min_age_months)) {
      setError("Das maximale Alter muss größer oder gleich dem minimalen Alter sein.");
      return;
    }
    if (Number(form.capacity_used) > Number(form.capacity_total)) {
      setError("Die Anzahl belegter Plätze darf die Gesamtkapazität nicht überschreiten.");
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        ...form,
        min_age_months: Number(form.min_age_months),
        max_age_months: Number(form.max_age_months),
        staff_count: Number(form.staff_count),
        capacity_total: Number(form.capacity_total),
        capacity_used: Number(form.capacity_used),
        qualification_hours: Number(form.qualification_hours),
        practicum_hours: Number(form.practicum_hours),
      };
      const saved =
        mode === "edit" ? await updateMyProvider(token, payload) : await createMyProvider(token, payload);
      const { is_certified, free_places, id, has_certificate, certificate_verified, ...editable } = saved;
      setForm(editable);
      setMode("edit");
      setHasCertificate(has_certificate);
      setCertificateVerified(certificate_verified);
      setSuccess(
        mode === "edit"
          ? "Ihre Änderungen wurden gespeichert."
          : `Profil für „${saved.name}" wurde angelegt${saved.is_certified ? " und als zertifiziert markiert" : ""}.`
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCertificateSelect(e) {
    const file = e.target.files?.[0];
    e.target.value = ""; // reset so re-selecting the same file still fires onChange
    if (!file) return;

    setCertError(null);
    setCertSuccess(null);
    if (!ALLOWED_CERTIFICATE_TYPES.includes(file.type)) {
      setCertError("Bitte nur PDF-, JPG- oder PNG-Dateien hochladen.");
      return;
    }
    if (file.size > MAX_CERTIFICATE_BYTES) {
      setCertError("Die Datei ist zu groß (maximal 5 MB).");
      return;
    }

    setCertBusy(true);
    try {
      const saved = await uploadMyCertificate(token, file);
      setHasCertificate(saved.has_certificate);
      setCertificateVerified(saved.certificate_verified);
      setCertSuccess("Zertifikat wurde hochgeladen. Ein Admin prüft es in Kürze.");
    } catch (err) {
      setCertError(err.message);
    } finally {
      setCertBusy(false);
    }
  }

  async function handleCertificateView() {
    setCertError(null);
    try {
      const { blob, filename } = await fetchMyCertificateBlob(token);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    } catch (err) {
      setCertError(err.message);
    }
  }

  async function handleCertificateDelete() {
    setCertError(null);
    setCertSuccess(null);
    setCertBusy(true);
    try {
      const saved = await deleteMyCertificate(token);
      setHasCertificate(saved.has_certificate);
      setCertificateVerified(saved.certificate_verified);
      setCertSuccess("Zertifikat wurde entfernt.");
    } catch (err) {
      setCertError(err.message);
    } finally {
      setCertBusy(false);
    }
  }

  const capMax = MAX_CAPACITY[form.care_type];

  if (loading) {
    return (
      <div className="section-head">
        <span className="eyebrow">Für Tagespflegepersonen</span>
        <h1>Mein Profil</h1>
        <p>Wird geladen …</p>
      </div>
    );
  }

  return (
    <div>
      <div className="section-head">
        <span className="eyebrow">Für Tagespflegepersonen</span>
        <h1>Mein Profil</h1>
        <p>
          {mode === "edit"
            ? "So sehen Eltern Ihr Profil. Ändern Sie Angaben und speichern Sie, um die Anzeige zu aktualisieren."
            : "Zeigen Sie Ihre Qualifikation, Pflegeerlaubnis und freien Plätze für suchende Eltern."}
        </p>
      </div>

      <div className="rules-note">
        Kindertagespflege (allein) erlaubt bis zu 5 Kinder. Großtagespflege — zwei bis drei Fachkräfte in
        gemeinsamen Räumen — erlaubt bis zu 10 Kinder. Diese Grenzen werden beim Speichern geprüft.
      </div>

      {error && <div className="form-error">{error}</div>}
      {success && <div className="form-success">{success}</div>}

      <form className="register-card" onSubmit={handleSubmit}>
        <div className="form-grid">
          <div className="field span-2">
            <label htmlFor="name">Name / Einrichtung</label>
            <input
              id="name"
              required
              value={form.name}
              onChange={(e) => update("name", e.target.value)}
              placeholder="z. B. Anke Möller"
            />
          </div>

          <div className="field">
            <label htmlFor="city">Ort</label>
            <input id="city" required value={form.city} onChange={(e) => update("city", e.target.value)} placeholder="z. B. Göttingen" />
          </div>

          <div className="field">
            <label htmlFor="care_type">Betreuungsform</label>
            <select id="care_type" value={form.care_type} onChange={(e) => update("care_type", e.target.value)}>
              <option value="individual">Kindertagespflege (allein, bis 5)</option>
              <option value="group">Großtagespflege (2–3 Fachkräfte, bis 10)</option>
            </select>
          </div>

          <div className="field">
            <label htmlFor="min_age">Alter von (Monate)</label>
            <input
              id="min_age"
              type="number"
              min="0"
              max="168"
              value={form.min_age_months}
              onChange={(e) => update("min_age_months", e.target.value)}
            />
          </div>

          <div className="field">
            <label htmlFor="max_age">Alter bis (Monate)</label>
            <input
              id="max_age"
              type="number"
              min="0"
              max="168"
              value={form.max_age_months}
              onChange={(e) => update("max_age_months", e.target.value)}
            />
          </div>

          <div className="field">
            <label htmlFor="staff_count">Anzahl Fachkräfte</label>
            <input
              id="staff_count"
              type="number"
              min={form.care_type === "individual" ? 1 : 2}
              max={form.care_type === "individual" ? 1 : 3}
              value={form.staff_count}
              onChange={(e) => update("staff_count", e.target.value)}
              disabled={form.care_type === "individual"}
            />
            <span className="form-hint">
              {form.care_type === "individual" ? "Immer 1 bei Kindertagespflege" : "2 oder 3 bei Großtagespflege"}
            </span>
          </div>

          <div className="field">
            <label htmlFor="capacity_total">Kapazität gesamt (max. {capMax})</label>
            <input
              id="capacity_total"
              type="number"
              min="1"
              max={capMax}
              value={form.capacity_total}
              onChange={(e) => update("capacity_total", e.target.value)}
            />
          </div>

          <div className="field">
            <label htmlFor="capacity_used">Bereits belegte Plätze</label>
            <input
              id="capacity_used"
              type="number"
              min="0"
              max={form.capacity_total}
              value={form.capacity_used}
              onChange={(e) => update("capacity_used", e.target.value)}
            />
          </div>

          <div className="field">
            <label htmlFor="qualification_hours">QHB-Unterrichtseinheiten</label>
            <input
              id="qualification_hours"
              type="number"
              min="0"
              value={form.qualification_hours}
              onChange={(e) => update("qualification_hours", e.target.value)}
            />
            <span className="form-hint">300 UE nötig für „zertifiziert"</span>
          </div>

          <div className="field">
            <label htmlFor="practicum_hours">Praktikumsstunden</label>
            <input
              id="practicum_hours"
              type="number"
              min="0"
              value={form.practicum_hours}
              onChange={(e) => update("practicum_hours", e.target.value)}
            />
            <span className="form-hint">80 Std. nötig für „zertifiziert"</span>
          </div>

          <div className="field span-2 checkbox-row">
            <input
              id="pflegeerlaubnis"
              type="checkbox"
              checked={form.has_pflegeerlaubnis}
              onChange={(e) => update("has_pflegeerlaubnis", e.target.checked)}
            />
            <label htmlFor="pflegeerlaubnis">Gültige Pflegeerlaubnis (§43 SGB VIII) liegt vor</label>
          </div>

          <div className="field span-2">
            <label htmlFor="bio">Kurzbeschreibung</label>
            <textarea
              id="bio"
              value={form.bio}
              onChange={(e) => update("bio", e.target.value)}
              placeholder="Erzählen Sie Eltern etwas über Ihre Betreuung, Räumlichkeiten und Schwerpunkte."
            />
          </div>

          <div className="field span-2">
            <label style={{ fontSize: "0.8rem", fontWeight: 700, color: "var(--forest-dark)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
              Kontaktdaten (optional)
            </label>
          </div>

          <div className="field">
            <label htmlFor="phone">Telefonnummer</label>
            <input
              id="phone"
              type="tel"
              value={form.phone}
              onChange={(e) => update("phone", e.target.value)}
              placeholder="z. B. 0551 123456"
            />
          </div>

          <div className="field">
            <label htmlFor="contact_email">E-Mail-Adresse</label>
            <input
              id="contact_email"
              type="email"
              value={form.contact_email}
              onChange={(e) => update("contact_email", e.target.value)}
              placeholder="kontakt@beispiel.de"
            />
          </div>

          <div className="field span-2">
            <label htmlFor="website">Website</label>
            <input
              id="website"
              type="url"
              value={form.website}
              onChange={(e) => update("website", e.target.value)}
              placeholder="https://www.beispiel.de"
            />
          </div>
        </div>

        <div className="form-actions">
          <button className="btn-primary" type="submit" disabled={submitting}>
            {submitting ? "Wird gespeichert …" : mode === "edit" ? "Änderungen speichern" : "Profil veröffentlichen"}
          </button>
        </div>
      </form>

      {mode === "edit" ? (
        <div className="register-card certificate-card">
          <h3>Qualifikationsnachweis</h3>
          <p className="form-hint certificate-hint">
            Laden Sie einen Nachweis Ihrer QHB-Qualifikation oder Pflegeerlaubnis hoch (PDF, JPG oder PNG, max. 5
            MB). Ein Admin prüft die Datei anschließend. Die Datei selbst ist nur für Sie und Admins sichtbar —
            Eltern sehen auf Ihrem Profil lediglich, ob ein Nachweis geprüft und bestätigt wurde.
          </p>

          {certError && <div className="form-error">{certError}</div>}
          {certSuccess && <div className="form-success">{certSuccess}</div>}

          <div className="badge-row certificate-status">
            {!hasCertificate ? (
              <span className="badge muted">Kein Zertifikat hochgeladen</span>
            ) : certificateVerified ? (
              <span className="badge verified">✓ Von Admin geprüft</span>
            ) : (
              <span className="badge honey">Hochgeladen — Prüfung ausstehend</span>
            )}
          </div>

          <input
            ref={certInputRef}
            type="file"
            accept="application/pdf,image/jpeg,image/png"
            onChange={handleCertificateSelect}
            hidden
          />
          <div className="form-actions certificate-actions">
            <button
              type="button"
              className="btn-primary"
              disabled={certBusy}
              onClick={() => certInputRef.current?.click()}
            >
              {certBusy ? "Wird hochgeladen …" : hasCertificate ? "Zertifikat ersetzen" : "Zertifikat hochladen"}
            </button>
            {hasCertificate && (
              <>
                <button type="button" className="btn-ghost" disabled={certBusy} onClick={handleCertificateView}>
                  Ansehen
                </button>
                <button type="button" className="btn-ghost" disabled={certBusy} onClick={handleCertificateDelete}>
                  Entfernen
                </button>
              </>
            )}
          </div>
        </div>
      ) : (
        <div className="rules-note certificate-note">
          Sobald Ihr Profil veröffentlicht ist, können Sie hier einen Qualifikationsnachweis hochladen.
        </div>
      )}
    </div>
  );
}
