import { useState } from "react";
import { createBooking } from "../api.js";
import { ELTERN_RATE_PER_HOUR, formatCurrency } from "../utils/format.js";

const INITIAL = {
  children: [{ name: "", age_months: "" }],
  start_date: "",
  start_hour: "8",
  end_hour: "16",
  parent_address: "",
  parent_phone: "",
  message: "",
};

// Mirrors BookingCreate.children's max_length in backend/app/models.py.
const MAX_CHILDREN = 10;

const HOUR_OPTIONS = Array.from({ length: 24 }, (_, h) => ({
  value: String(h),
  label: `${String(h).padStart(2, "0")}:00`,
}));

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

// Server-side wording for the two date/time business-rule rejections (see
// create_booking in main.py) — matched against err.message so a rejection
// that only the server catches (e.g. the clock ticking past while the form
// was open) still highlights the right fields, not just client-side misses.
const DATE_ERROR_HINTS = ["Zukunft", "Startzeit", "Endzeit"];

// Lets a logged-in Eltern account send a booking request for this provider.
// Only shown/usable when the provider has an account-linked owner (see
// `is_bookable` on the public provider dict) — otherwise there's nobody who
// could ever confirm the request.
export default function BookingRequestForm({ provider, auth, onGoToLogin }) {
  const [form, setForm] = useState(INITIAL);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [dateError, setDateError] = useState(false);
  const [sent, setSent] = useState(false);

  const previewHours = Math.max(0, Number(form.end_hour) - Number(form.start_hour));

  const set = (key, value) => {
    setForm((f) => ({ ...f, [key]: value }));
    if (["start_date", "start_hour", "end_hour"].includes(key)) {
      setDateError(false);
      setError(null);
    }
  };

  const updateChild = (index, key, value) => {
    setForm((f) => ({
      ...f,
      children: f.children.map((c, i) => (i === index ? { ...c, [key]: value } : c)),
    }));
  };

  const addChild = () => {
    setForm((f) =>
      f.children.length >= MAX_CHILDREN ? f : { ...f, children: [...f.children, { name: "", age_months: "" }] }
    );
  };

  const removeChild = (index) => {
    setForm((f) => (f.children.length <= 1 ? f : { ...f, children: f.children.filter((_, i) => i !== index) }));
  };

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setDateError(false);

    const startHour = Number(form.start_hour);
    const endHour = Number(form.end_hour);
    if (endHour <= startHour) {
      setError("Die Endzeit muss nach der Startzeit liegen.");
      setDateError(true);
      return;
    }
    const requestedStart = new Date(`${form.start_date}T${String(startHour).padStart(2, "0")}:00:00`);
    if (requestedStart <= new Date()) {
      setError("Der gewünschte Termin muss in der Zukunft liegen.");
      setDateError(true);
      return;
    }

    setSubmitting(true);
    try {
      await createBooking(auth.token, {
        provider_id: provider.id,
        children: form.children.map((c) => ({
          name: c.name,
          age_months: c.age_months === "" ? null : Number(c.age_months),
        })),
        start_date: form.start_date,
        start_hour: startHour,
        end_hour: endHour,
        parent_address: form.parent_address,
        parent_phone: form.parent_phone,
        message: form.message || null,
      });
      setSent(true);
    } catch (err) {
      setError(err.message);
      setDateError(DATE_ERROR_HINTS.some((hint) => err.message.includes(hint)));
    } finally {
      setSubmitting(false);
    }
  }

  if (!auth) {
    return (
      <div className="booking-hint">
        <p>Bitte melden Sie sich mit einem Eltern-Konto an, um eine Buchungsanfrage zu senden.</p>
        <button type="button" className="btn-primary" onClick={onGoToLogin}>
          Jetzt anmelden
        </button>
      </div>
    );
  }

  if (auth.role !== "eltern") {
    return (
      <div className="booking-hint">
        <p>Buchungsanfragen können nur mit einem Eltern-Konto gesendet werden.</p>
      </div>
    );
  }

  if (!provider.is_bookable) {
    return (
      <div className="booking-hint">
        <p>Dieser Anbieter hat noch kein verknüpftes Konto — Buchungsanfragen sind derzeit nicht möglich.</p>
      </div>
    );
  }

  if (sent) {
    return (
      <div className="form-success">
        Ihre Buchungsanfrage wurde gesendet. Sie finden den Status unter „Meine Anfragen" und werden
        benachrichtigt, sobald {provider.name} antwortet.
      </div>
    );
  }

  return (
    <form className="booking-form" onSubmit={handleSubmit}>
      {provider.free_places === 0 && (
        <p className="form-hint">Aktuell keine freien Plätze — Ihre Anfrage wird als Warteliste vermerkt.</p>
      )}
      <div className="form-grid">
        {form.children.map((child, index) => (
          <div className="field span-2 child-row" key={index}>
            <div className="field">
              <label htmlFor={`child_name_${index}`}>
                Name des Kindes{form.children.length > 1 ? ` ${index + 1}` : ""}
              </label>
              <input
                id={`child_name_${index}`}
                required
                value={child.name}
                onChange={(e) => updateChild(index, "name", e.target.value)}
                placeholder="z. B. Mia"
              />
            </div>
            <div className="field">
              <label htmlFor={`child_age_months_${index}`}>Alter (Monate)</label>
              <input
                id={`child_age_months_${index}`}
                type="number"
                min="0"
                max="216"
                value={child.age_months}
                onChange={(e) => updateChild(index, "age_months", e.target.value)}
              />
            </div>
            {form.children.length > 1 && (
              <button
                type="button"
                className="btn-ghost btn-small remove-child-btn"
                onClick={() => removeChild(index)}
              >
                Entfernen
              </button>
            )}
          </div>
        ))}
        {form.children.length < MAX_CHILDREN && (
          <div className="field span-2">
            <button type="button" className="link-btn" onClick={addChild}>
              + Weiteres Kind hinzufügen
            </button>
          </div>
        )}

        <div className={`field ${dateError ? "field-error" : ""}`}>
          <label htmlFor="start_date">Gewünschter Start</label>
          <input
            id="start_date"
            type="date"
            required
            min={todayISO()}
            value={form.start_date}
            onChange={(e) => set("start_date", e.target.value)}
          />
        </div>
        <div className={`field span-2 hour-range ${dateError ? "field-error" : ""}`}>
          <div className="field">
            <label htmlFor="start_hour">Von</label>
            <select id="start_hour" value={form.start_hour} onChange={(e) => set("start_hour", e.target.value)}>
              {HOUR_OPTIONS.map((h) => (
                <option key={h.value} value={h.value}>
                  {h.label}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="end_hour">Bis</label>
            <select id="end_hour" value={form.end_hour} onChange={(e) => set("end_hour", e.target.value)}>
              {HOUR_OPTIONS.map((h) => (
                <option key={h.value} value={h.value}>
                  {h.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        {previewHours > 0 && (
          <p className="form-hint span-2">
            Geschätzter Betrag: <strong>{formatCurrency(previewHours * ELTERN_RATE_PER_HOUR)}</strong> ({previewHours}{" "}
            Std. à {formatCurrency(ELTERN_RATE_PER_HOUR)}) — die genaue Endabrechnung erfolgt bei Bestätigung.
          </p>
        )}

        <div className="field span-2">
          <label htmlFor="parent_address">Ihre Adresse</label>
          <input
            id="parent_address"
            required
            value={form.parent_address}
            onChange={(e) => set("parent_address", e.target.value)}
            placeholder="Straße, Hausnummer, PLZ, Ort"
          />
        </div>
        <div className="field">
          <label htmlFor="parent_phone">Ihre Telefonnummer</label>
          <input
            id="parent_phone"
            type="tel"
            required
            value={form.parent_phone}
            onChange={(e) => set("parent_phone", e.target.value)}
            placeholder="z. B. 0551 123456"
          />
        </div>

        <div className="field span-2">
          <label htmlFor="booking_message">Nachricht (optional)</label>
          <textarea
            id="booking_message"
            value={form.message}
            onChange={(e) => set("message", e.target.value)}
            placeholder="Erzählen Sie kurz etwas zu Ihrem Betreuungswunsch."
          />
        </div>
      </div>
      {error && <div className="form-error">{error}</div>}
      <div className="form-actions">
        <button className="btn-primary" type="submit" disabled={submitting}>
          {submitting ? "Wird gesendet …" : "Buchungsanfrage senden"}
        </button>
      </div>
    </form>
  );
}
