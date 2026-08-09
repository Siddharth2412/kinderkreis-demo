export function formatAge(minMonths, maxMonths, { short = false } = {}) {
  const fmt = (m) =>
    m < 24
      ? `${m}${short ? " Mon." : " Monate"}`
      : `${Math.floor(m / 12)}${short ? " J." : " Jahre"}`;
  const sep = short ? " – " : " bis ";
  return `${fmt(minMonths)}${sep}${fmt(maxMonths)}`;
}
