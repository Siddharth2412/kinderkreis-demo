import { useState } from "react";
import { registerProvider } from "../api.js";

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

export default function RegisterView({ onRegistered }) {
  const [form, setForm] = useState(INITIAL);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [submitting, setSubmitting] = useState(false);

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
      const created = await registerProvider(payload);
      setSuccess(`Profil für „${created.name}" wurde angelegt${created.is_certified ? " und als zertifiziert markiert" : ""}.`);
      setForm(INITIAL);
      onRegistered?.(created);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  const capMax = MAX_CAPACITY[form.care_type];

  return (
    <div>
      <div className="section-head">
        <span className="eyebrow">Für Tagespflegepersonen</span>
        <h1>Profil anlegen</h1>
        <p>Zeigen Sie Ihre Qualifikation, Pflegeerlaubnis und freien Plätze für suchende Eltern.</p>
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
            {submitting ? "Wird gespeichert …" : "Profil veröffentlichen"}
          </button>
        </div>
      </form>
    </div>
  );
}
