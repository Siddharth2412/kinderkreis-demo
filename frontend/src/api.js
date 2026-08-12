const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const message =
      typeof body.detail === "string"
        ? body.detail
        : Array.isArray(body.detail)
        ? body.detail.map((d) => d.msg).join(", ")
        : `Anfrage fehlgeschlagen (${res.status})`;
    throw new Error(message);
  }
  return res.json();
}

export const fetchProviders = (filters = {}) => {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") params.set(k, v);
  });
  const q = params.toString();
  return request(`/api/providers${q ? `?${q}` : ""}`);
};

export const fetchCities = () => request("/api/meta/cities");

// Tagespflegeperson's own profile — requires an authenticated session, mapped
// to their account by email on the backend. Not part of the public directory.
export const fetchMyProvider = (token) =>
  request("/api/providers/me", { headers: authHeaders(token) });

export const createMyProvider = (token, payload) =>
  request("/api/providers/me", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });

export const updateMyProvider = (token, payload) =>
  request("/api/providers/me", {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });

export const loginUser = (email, password) =>
  request("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });

export const registerUser = (name, email, password, role = "eltern") =>
  request("/api/auth/register", { method: "POST", body: JSON.stringify({ name, email, password, role }) });

export const logoutUser = (token) =>
  request("/api/auth/logout", { method: "POST", body: JSON.stringify({ token }) });

export const verifyEmail = (email, otp) =>
  request("/api/auth/verify-email", { method: "POST", body: JSON.stringify({ email, otp }) });

export const resendVerification = (email) =>
  request("/api/auth/resend-verification", { method: "POST", body: JSON.stringify({ email }) });

export const forgotPassword = (email) =>
  request("/api/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) });

export const resetPassword = (email, otp, new_password) =>
  request("/api/auth/reset-password", { method: "POST", body: JSON.stringify({ email, otp, new_password }) });

// Bookings — Eltern request care from an account-linked provider, the owning
// Tagespflegeperson confirms/declines.
export const createBooking = (token, payload) =>
  request("/api/bookings", { method: "POST", headers: authHeaders(token), body: JSON.stringify(payload) });

export const fetchMyBookings = (token) =>
  request("/api/bookings/mine", { headers: authHeaders(token) });

export const cancelBooking = (token, id) =>
  request(`/api/bookings/${id}/cancel`, { method: "POST", headers: authHeaders(token) });

export const fetchProviderBookings = (token) =>
  request("/api/bookings/provider", { headers: authHeaders(token) });

export const confirmBooking = (token, id) =>
  request(`/api/bookings/${id}/confirm`, { method: "POST", headers: authHeaders(token) });

export const declineBooking = (token, id) =>
  request(`/api/bookings/${id}/decline`, { method: "POST", headers: authHeaders(token) });

// Notifications — in-app only, shared by both roles.
export const fetchNotifications = (token) =>
  request("/api/notifications", { headers: authHeaders(token) });

export const markNotificationRead = (token, id) =>
  request(`/api/notifications/${id}/read`, { method: "POST", headers: authHeaders(token) });

export const markAllNotificationsRead = (token) =>
  request("/api/notifications/read-all", { method: "POST", headers: authHeaders(token) });
