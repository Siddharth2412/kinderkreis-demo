import { useEffect, useState } from "react";
import { fetchProviderBookings, confirmBooking, declineBooking } from "../api.js";
import { formatBookingStatus, formatChildrenLabel, formatCurrency, formatDate, formatHourRange } from "../utils/format.js";

// "Buchungsanfragen" — incoming booking requests for the logged-in
// Tagespflegeperson's own profile (mapped via db.get_provider_by_owner on
// the backend, same account-mapping as ProfileView).
export default function ProviderBookingsView({ token, onGoToProfile }) {
  const [bookings, setBookings] = useState([]);
  const [hasProfile, setHasProfile] = useState(true);
  const [totalAmountToReceive, setTotalAmountToReceive] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);
  // Declining requires a reason (see BookingDeclineRequest in the backend),
  // so "Ablehnen" opens an inline reason field for this booking's id instead
  // of firing the request immediately.
  const [declineTargetId, setDeclineTargetId] = useState(null);
  const [declineReason, setDeclineReason] = useState("");

  function load() {
    setLoading(true);
    setError(null);
    fetchProviderBookings(token)
      .then((data) => {
        setBookings(data.bookings);
        setHasProfile(data.has_profile);
        setTotalAmountToReceive(data.total_amount_to_receive);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(load, [token]);

  async function handleConfirm(id) {
    setBusyId(id);
    try {
      await confirmBooking(token, id);
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  function startDecline(id) {
    setDeclineTargetId(id);
    setDeclineReason("");
    setError(null);
  }

  function cancelDecline() {
    setDeclineTargetId(null);
    setDeclineReason("");
  }

  async function submitDecline(id) {
    if (!declineReason.trim()) {
      setError("Bitte geben Sie einen Grund für die Ablehnung an.");
      return;
    }
    setBusyId(id);
    try {
      await declineBooking(token, id, declineReason.trim());
      setDeclineTargetId(null);
      setDeclineReason("");
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
        <>
          <p className="result-count">
            Gesamtbetrag offener und bestätigter Buchungen: <strong>{formatCurrency(totalAmountToReceive)}</strong>
          </p>
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
                    {formatChildrenLabel(b.children)} · {formatDate(b.start_date)},{" "}
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
                  {b.status === "pending" && declineTargetId !== b.id && (
                    <div className="form-actions">
                      <button
                        className="btn-primary btn-small"
                        onClick={() => handleConfirm(b.id)}
                        disabled={busyId === b.id}
                      >
                        {busyId === b.id ? "…" : "Bestätigen"}
                      </button>
                      <button
                        className="btn-ghost btn-small"
                        onClick={() => startDecline(b.id)}
                        disabled={busyId === b.id}
                      >
                        Ablehnen
                      </button>
                    </div>
                  )}
                  {b.status === "pending" && declineTargetId === b.id && (
                    <div className="decline-reason-form">
                      <textarea
                        className="decline-reason-input"
                        value={declineReason}
                        onChange={(e) => setDeclineReason(e.target.value)}
                        placeholder="Grund für die Ablehnung (wird den Eltern angezeigt)"
                        autoFocus
                      />
                      <div className="form-actions">
                        <button
                          className="btn-primary btn-small"
                          onClick={() => submitDecline(b.id)}
                          disabled={busyId === b.id}
                        >
                          {busyId === b.id ? "Wird gesendet …" : "Ablehnung senden"}
                        </button>
                        <button className="btn-ghost btn-small" onClick={cancelDecline} disabled={busyId === b.id}>
                          Abbrechen
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
