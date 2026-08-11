export function formatAge(minMonths, maxMonths, { short = false } = {}) {
  const fmt = (m) =>
    m < 24
      ? `${m}${short ? " Mon." : " Monate"}`
      : `${Math.floor(m / 12)}${short ? " J." : " Jahre"}`;
  const sep = short ? " – " : " bis ";
  return `${fmt(minMonths)}${sep}${fmt(maxMonths)}`;
}

const BOOKING_STATUS = {
  pending: { label: "Angefragt", className: "badge honey" },
  confirmed: { label: "Bestätigt", className: "badge" },
  declined: { label: "Abgelehnt", className: "badge muted" },
  cancelled: { label: "Storniert", className: "badge muted" },
};

export function formatBookingStatus(status) {
  return BOOKING_STATUS[status] || { label: status, className: "badge muted" };
}

export function formatDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export function formatHourRange(startHour, endHour) {
  const pad = (h) => String(h).padStart(2, "0");
  return `${pad(startHour)}:00–${pad(endHour)}:00 Uhr`;
}
