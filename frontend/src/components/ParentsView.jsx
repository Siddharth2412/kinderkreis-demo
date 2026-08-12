import { useEffect, useState } from "react";
import { fetchCities, fetchProviders } from "../api.js";
import ProviderCard from "./ProviderCard.jsx";
import ProviderDetailModal from "./ProviderDetailModal.jsx";

const AGE_OPTIONS = [
  { label: "Alle Altersgruppen", value: "" },
  { label: "0–1 Jahr", value: 6 },
  { label: "1–2 Jahre", value: 18 },
  { label: "2–3 Jahre", value: 30 },
  { label: "3–5 Jahre", value: 48 },
  { label: "5–14 Jahre", value: 84 },
];

export default function ParentsView({ auth, onGoToLogin }) {
  const [cities, setCities] = useState([]);
  const [filters, setFilters] = useState({
    city: "",
    care_type: "",
    age_months: "",
    available_only: false,
    certified_only: false,
  });
  const [providers, setProviders] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchCities()
      .then((data) => setCities(data.cities))
      .catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchProviders(filters)
      .then((data) => setProviders(data.providers))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [filters]);

  const updateFilter = (key, value) => setFilters((f) => ({ ...f, [key]: value }));

  return (
    <div>
      <div className="section-head">
        <span className="eyebrow">Für Eltern</span>
        <h1>Betreuung in Ihrer Nähe finden</h1>
        <p>Filtern Sie nach Ort, Alter Ihres Kindes und Betreuungsform, um passende Profile zu sehen.</p>
      </div>

      <div className="filters">
        <div className="field">
          <label htmlFor="city">Ort</label>
          <select id="city" value={filters.city} onChange={(e) => updateFilter("city", e.target.value)}>
            <option value="">Alle Orte</option>
            {cities.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label htmlFor="age">Alter des Kindes</label>
          <select id="age" value={filters.age_months} onChange={(e) => updateFilter("age_months", e.target.value)}>
            {AGE_OPTIONS.map((opt) => (
              <option key={opt.label} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label htmlFor="care_type">Betreuungsform</label>
          <select
            id="care_type"
            value={filters.care_type}
            onChange={(e) => updateFilter("care_type", e.target.value)}
          >
            <option value="">Alle Formen</option>
            <option value="individual">Kindertagespflege (bis 5)</option>
            <option value="group">Großtagespflege (bis 10)</option>
          </select>
        </div>

        {/* Grouped in one wrapper so the two checkboxes move as a pair —
            previously each was its own flex item, so the wider filter box
            fit "Nur freie Plätze" onto row 1 next to the selects while "Nur
            zertifiziert" wrapped alone onto row 2, splitting them apart. */}
        <div className="filters-checks">
          <div className="field checkbox">
            <input
              type="checkbox"
              id="available"
              checked={filters.available_only}
              onChange={(e) => updateFilter("available_only", e.target.checked)}
            />
            <label htmlFor="available">Nur freie Plätze</label>
          </div>

          <div className="field checkbox">
            <input
              type="checkbox"
              id="certified"
              checked={filters.certified_only}
              onChange={(e) => updateFilter("certified_only", e.target.checked)}
            />
            <label htmlFor="certified">Nur zertifiziert</label>
          </div>
        </div>
      </div>

      {error && <div className="form-error">{error}</div>}

      {!loading && !error && (
        <p className="result-count">
          {providers.length} {providers.length === 1 ? "Profil gefunden" : "Profile gefunden"}
        </p>
      )}

      {loading ? (
        <p className="result-count">Lade Profile …</p>
      ) : providers.length === 0 ? (
        <div className="empty-state">Keine Profile für diese Auswahl gefunden. Versuchen Sie es mit weniger Filtern.</div>
      ) : (
        <div className="directory">
          {providers.map((p) => (
            <ProviderCard key={p.id} provider={p} onSelect={setSelected} />
          ))}
        </div>
      )}

      <ProviderDetailModal
        provider={selected}
        auth={auth}
        onClose={() => setSelected(null)}
        onGoToLogin={onGoToLogin}
      />
    </div>
  );
}
