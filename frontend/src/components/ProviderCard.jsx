import { formatAge } from "../utils/format.js";

const AVATAR_COLORS = ["#1F3D2B", "#C98B22", "#52655B", "#2E4F3A", "#B3452E"];

function initials(name) {
  return name
    .replace(/["""„]/g, "")
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();
}

export default function ProviderCard({ provider, onSelect }) {
  const color = AVATAR_COLORS[provider.id % AVATAR_COLORS.length];
  const dots = Array.from({ length: provider.capacity_total }, (_, i) => i < provider.capacity_used);

  return (
    <button className="provider-card" onClick={() => onSelect(provider)}>
      <div className="provider-top">
        <div className="avatar" style={{ background: color }}>
          {initials(provider.name)}
        </div>
        <div>
          <div className="provider-name">{provider.name}</div>
          <div className="provider-city">
            {provider.city} · {formatAge(provider.min_age_months, provider.max_age_months, { short: true })}
          </div>
        </div>
      </div>

      <div className="badge-row">
        {provider.certificate_verified && <span className="badge verified">✓ Geprüft</span>}
        {provider.is_certified ? (
          <span className="badge">Zertifiziert</span>
        ) : (
          <span className="badge muted">In Qualifizierung</span>
        )}
        {provider.has_pflegeerlaubnis ? (
          <span className="badge honey">Pflegeerlaubnis</span>
        ) : (
          <span className="badge muted">Erlaubnis ausstehend</span>
        )}
        {provider.care_type === "group" && (
          <span className="badge honey">{provider.staff_count} Fachkräfte</span>
        )}
      </div>

      <div className="capacity-row">
        <span>
          {provider.capacity_used} / {provider.capacity_total} Plätze belegt
        </span>
        <span className="capacity-dots">
          {dots.map((filled, i) => (
            <span key={i} className={filled ? "filled" : ""} />
          ))}
        </span>
      </div>
    </button>
  );
}
