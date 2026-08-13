import { useEffect, useState } from "react";
import { fetchProviderBookings, confirmBooking, declineBooking } from "../api.js";
import { formatBookingStatus, formatCurrency, formatDate, formatHourRange } from "../utils/format.js";

// "Buchungsanfragen" — incoming booking requests for the logged-in
// Tagespflegeperson's own profile (mapped via db.get_provider_by_owner on
// the backend, same account-mapping as ProfileView).
export default function ProviderBookingsView({ token, onGoToProfile }) {
  const [bookings, setBookings] = useState([]);
  const [hasProfile, setHasProfile] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);

  function load() {
    setLoading(true);
    setError(null);
    fetchProviderBookings(token)
      .then((data) => {
        setBookings(data.bookings);
        setHasProfile(data.has_profile);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(load, [token]);

  async function handleDecision(id, action) {
    setBusyId(id);
    try {
      await (action === "confirm" ? confirmBooking(token, id) : declineBooking(token, id));
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <div className="section-head">
        <span className="eyebrow">Für Tagespflegepersonen</span>
        <h1>Buchungsanfragen</h1>
        <p>Anfragen von Eltern für Ihr Profil — bestätigen oder ablehnen.</p>
      </div>

      {error && <div className="form-error">{error}</div>}

      {loading ? (
        <p className="result-count">Wird geladen …</p>
      ) : !hasProfile ? (
        <div className="empty-state">
          Sie haben noch kein Profil angelegt.{" "}
          <button className="link-btn" onClick={onGoToProfile}>
            Jetzt Profil anlegen
          </button>
          , damit Eltern Sie buchen können.
        </div>
      ) : bookings.length === 0 ? (
        <div className="empty-state">Noch keine Buchungsanfragen erhalten.</div>
      ) : (
        <div className="booking-list">
          {bookings.map((b) => {
            const status = formatBookingStatus(b.status);
            return (
              <div className="booking-card" key={b.id}>
                <div className="booking-card-head">
                  <div>
                    <div className="provider-name">{b.parent_name || b.parent_email}</div>
                    <div className="provider-city">{b.parent_email}</div>
                  </div>
                  <span className={status.className}>{status.label}</span>
                </div>
                <p className="modal-bio">
                  {b.child_name}
                  {b.child_age_months != null ? ` (${b.child_age_months} Monate)` : ""} · {formatDate(b.start_date)},{" "}
                  {formatHourRange(b.start_hour, b.end_hour)}
                </p>
                <p className="booking-meta">
                  📍 {b.parent_address} · 📞 {b.parent_phone}
                </p>
                <p className="booking-meta">
                  Sie erhalten: <strong>{formatCurrency(b.amount_to_receive)}</strong> ({b.duration_hours} Std. à
                  18,00 €)
                </p>
                {b.message && <p className="modal-bio">„{b.message}"</p>}
                {b.status === "pending" && (
                  <div className="form-actions">
                    <button
                      className="btn-primary btn-small"
                      onClick={() => handleDecision(b.id, "confirm")}
                      disabled={busyId === b.id}
                    >
                      {busyId === b.id ? "…" : "Bestätigen"}
                    </button>
                    <button
                      className="btn-ghost btn-small"
                      onClick={() => handleDecision(b.id, "decline")}
                      disabled={busyId === b.id}
                    >
                      Ablehnen
                    </button>
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
