import { useEffect, useState } from "react";
import { fetchMyBookings, cancelBooking } from "../api.js";
import { formatBookingStatus, formatDate, formatHourRange } from "../utils/format.js";

// "Meine Anfragen" — an Eltern account's own booking requests and their
// status. Mapped to the account via the session token, same shape as
// ProfileView's "own profile" fetch.
export default function MyBookingsView({ token }) {
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);

  function load() {
    setLoading(true);
    setError(null);
    fetchMyBookings(token)
      .then((data) => setBookings(data.bookings))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(load, [token]);

  async function handleCancel(id) {
    setBusyId(id);
    try {
      await cancelBooking(token, id);
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
        <span className="eyebrow">Für Eltern</span>
        <h1>Meine Anfragen</h1>
        <p>Der Status Ihrer Buchungsanfragen an Tagespflegepersonen.</p>
      </div>

      {error && <div className="form-error">{error}</div>}

      {loading ? (
        <p className="result-count">Wird geladen …</p>
      ) : bookings.length === 0 ? (
        <div className="empty-state">
          Noch keine Buchungsanfragen gesendet. Öffnen Sie ein Profil im Verzeichnis, um eine Anfrage zu stellen.
        </div>
      ) : (
        <div className="booking-list">
          {bookings.map((b) => {
            const status = formatBookingStatus(b.status);
            return (
              <div className="booking-card" key={b.id}>
                <div className="booking-card-head">
                  <div>
                    <div className="provider-name">{b.provider_name}</div>
                    <div className="provider-city">{b.provider_city}</div>
                  </div>
                  <span className={status.className}>{status.label}</span>
                </div>
                <p className="modal-bio">
                  {b.child_name}
                  {b.child_age_months != null ? ` (${b.child_age_months} Monate)` : ""} · {formatDate(b.start_date)},{" "}
                  {formatHourRange(b.start_hour, b.end_hour)}
                </p>
                <p className="booking-meta">
                  {b.parent_address} · {b.parent_phone}
                </p>
                {b.message && <p className="modal-bio">„{b.message}"</p>}
                {(b.status === "pending" || b.status === "confirmed") && (
                  <div className="form-actions">
                    <button
                      className="btn-ghost btn-small"
                      onClick={() => handleCancel(b.id)}
                      disabled={busyId === b.id}
                    >
                      {busyId === b.id
                        ? "Wird storniert …"
                        : b.status === "confirmed"
                        ? "Buchung stornieren"
                        : "Anfrage zurückziehen"}
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
