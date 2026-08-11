import { formatAge } from "../utils/format.js";
import BookingRequestForm from "./BookingRequestForm.jsx";

function freePlacesLabel(n) {
  if (n === 0) return "Aktuell keine freien Plätze.";
  return `${n} freie${n === 1 ? "r" : ""} Platz${n === 1 ? "" : "e"} verfügbar.`;
}

export default function ProviderDetailModal({ provider, auth, onClose, onGoToLogin }) {
  if (!provider) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose} aria-label="Schließen">
          ✕
        </button>
        <h2>{provider.name}</h2>
        <div className="provider-city">
          {provider.city} · Betreut Kinder von {formatAge(provider.min_age_months, provider.max_age_months)}
        </div>

        <div className="badge-row">
          {provider.is_certified ? (
            <span className="badge">Zertifiziert (QHB)</span>
          ) : (
            <span className="badge muted">In Qualifizierung</span>
          )}
          {provider.has_pflegeerlaubnis ? (
            <span className="badge honey">Pflegeerlaubnis §43 SGB VIII</span>
          ) : (
            <span className="badge muted">Erlaubnis ausstehend</span>
          )}
          <span className="badge muted">
            {provider.care_type === "individual" ? "Kindertagespflege" : "Großtagespflege"}
          </span>
        </div>

        {provider.bio && (
          <div className="modal-section">
            <h3>Über die Betreuung</h3>
            <p className="modal-bio">{provider.bio}</p>
          </div>
        )}

        <div className="modal-section">
          <h3>Qualifikation</h3>
          <p className="modal-bio">
            {provider.qualification_hours} von 300 UE nach QHB absolviert · {provider.practicum_hours} von 80 Praktikumsstunden.
          </p>
        </div>

        <div className="modal-section">
          <h3>Kapazität</h3>
          <p className="modal-bio">
            {provider.capacity_used} von {provider.capacity_total} Plätzen belegt
            {provider.staff_count > 1 ? ` · betreut von ${provider.staff_count} Fachkräften gemeinsam` : ""}.{" "}
            {freePlacesLabel(provider.free_places)}
          </p>
        </div>

        {(provider.phone || provider.contact_email || provider.website) && (
          <div className="modal-section">
            <h3>Kontakt</h3>
            <div className="contact-list">
              {provider.phone && (
                <a className="contact-item" href={`tel:${provider.phone}`}>
                  <span className="contact-icon">📞</span> {provider.phone}
                </a>
              )}
              {provider.contact_email && (
                <a className="contact-item" href={`mailto:${provider.contact_email}`}>
                  <span className="contact-icon">✉️</span> {provider.contact_email}
                </a>
              )}
              {provider.website && (
                <a className="contact-item" href={provider.website} target="_blank" rel="noopener noreferrer">
                  <span className="contact-icon">🌐</span> {provider.website.replace(/^https?:\/\//, "")}
                </a>
              )}
            </div>
          </div>
        )}

        <div className="modal-section">
          <h3>Buchungsanfrage</h3>
          <BookingRequestForm
            provider={provider}
            auth={auth}
            onGoToLogin={() => {
              onClose();
              onGoToLogin();
            }}
          />
        </div>
      </div>
    </div>
  );
}
