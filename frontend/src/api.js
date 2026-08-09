const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
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

export const fetchProvider = (id) => request(`/api/providers/${id}`);

export const fetchCities = () => request("/api/meta/cities");

export const registerProvider = (payload) =>
  request("/api/providers", { method: "POST", body: JSON.stringify(payload) });

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
