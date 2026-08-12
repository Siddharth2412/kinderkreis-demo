import { useState, useEffect } from "react";
import LandingView from "./components/LandingView.jsx";
import ParentsView from "./components/ParentsView.jsx";
import ProfileView from "./components/ProfileView.jsx";
import LoginView from "./components/LoginView.jsx";
import SignupView from "./components/SignupView.jsx";
import ForgotPasswordView from "./components/ForgotPasswordView.jsx";
import VerifyEmailView from "./components/VerifyEmailView.jsx";
import MyBookingsView from "./components/MyBookingsView.jsx";
import ProviderBookingsView from "./components/ProviderBookingsView.jsx";
import NotificationBell from "./components/NotificationBell.jsx";
import AdminLoginView from "./components/AdminLoginView.jsx";
import AdminPanelView from "./components/AdminPanelView.jsx";
import { logoutUser, adminLogout } from "./api.js";

const STORAGE_KEY = "kk_auth";
const ADMIN_STORAGE_KEY = "kk_admin_auth"; // separate storage — never mixed with the eltern/tagespflege session
const AUTH_VIEWS = ["login", "signup", "verify", "forgot"];

function loadAuth() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function loadAdminAuth() {
  try {
    const raw = localStorage.getItem(ADMIN_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export default function App() {
  // Not logged in → the marketing landing page is the front door. Already
  // has a session from localStorage → skip straight to the directory, same
  // as before this page existed.
  const [view, setView] = useState(() => (loadAuth() ? "home" : "landing"));
  const [auth, setAuth] = useState(loadAuth);
  const [pendingEmail, setPendingEmail] = useState("");
  const [adminAuth, setAdminAuth] = useState(loadAdminAuth);

  useEffect(() => {
    if (auth) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(auth));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, [auth]);

  useEffect(() => {
    if (adminAuth) {
      localStorage.setItem(ADMIN_STORAGE_KEY, JSON.stringify(adminAuth));
    } else {
      localStorage.removeItem(ADMIN_STORAGE_KEY);
    }
  }, [adminAuth]);

  function handleLogin(user) {
    setAuth(user);
    setPendingEmail("");
    setView("home");
  }

  function handleNeedsVerification(email) {
    setPendingEmail(email);
    setView("verify");
  }

  async function handleLogout() {
    if (auth) await logoutUser(auth.token).catch(() => {});
    setAuth(null);
    setView("landing");
  }

  // Logo / "Startseite": logged-in users land on the directory (as before);
  // logged-out visitors go back to the landing page, not straight into it.
  function goHome() {
    setView(auth ? "home" : "landing");
  }

  function handleAdminLogin(admin) {
    setAdminAuth(admin);
  }

  async function handleAdminLogout() {
    if (adminAuth) await adminLogout(adminAuth.token).catch(() => {});
    setAdminAuth(null);
    setView("home");
  }

  // The directory (Für Eltern) now requires a session — eltern or
  // tagespflege, either works — logged-out visitors only ever see the
  // landing page and have to log in or register first. `!!auth` is the
  // load-bearing check here, not just "not one of the other views": with
  // it gone, any bug that leaves `view` on something unexpected (or a
  // stale localStorage session that fails to load) would fall through to
  // showing the directory to a logged-out visitor.
  const showLanding = view === "landing";
  const showProfile = view === "profile" && auth?.role === "tagespflege";
  const showMyBookings = view === "bookings" && auth?.role === "eltern";
  const showProviderBookings = view === "provider-bookings" && auth?.role === "tagespflege";
  const showAdmin = view === "admin";
  const showDirectory =
    !!auth &&
    !showLanding &&
    !AUTH_VIEWS.includes(view) &&
    !showProfile &&
    !showMyBookings &&
    !showProviderBookings &&
    !showAdmin;

  return (
    <>
      <nav>
        <div className="wrap">
          <button type="button" className="logo" onClick={goHome}>
            <span className="logo-mark"></span>Kinderkreis
          </button>
          <div className="nav-links">
            <button
              className={`nav-btn ${view === "home" || view === "landing" ? "active" : ""}`}
              onClick={goHome}
            >
              Startseite
            </button>
            {auth ? (
              <div className="nav-user">
                {auth.role === "eltern" && (
                  <button
                    className={`nav-btn ${view === "bookings" ? "active" : ""}`}
                    onClick={() => setView("bookings")}
                  >
                    Meine Anfragen
                  </button>
                )}
                {auth.role === "tagespflege" && (
                  <>
                    <button
                      className={`nav-btn ${view === "profile" ? "active" : ""}`}
                      onClick={() => setView("profile")}
                    >
                      Profil bearbeiten
                    </button>
                    <button
                      className={`nav-btn ${view === "provider-bookings" ? "active" : ""}`}
                      onClick={() => setView("provider-bookings")}
                    >
                      Buchungsanfragen
                    </button>
                  </>
                )}
                <NotificationBell token={auth.token} />
                <span className="nav-user-name">{auth.name}</span>
                <button className="btn-ghost btn-small" onClick={handleLogout}>
                  Abmelden
                </button>
              </div>
            ) : (
              <>
                <button
                  className={`nav-btn ${view === "login" ? "active" : ""}`}
                  onClick={() => setView("login")}
                >
                  Anmelden
                </button>
                <button
                  className="btn-primary btn-small"
                  onClick={() => setView("signup")}
                >
                  Registrieren
                </button>
              </>
            )}
          </div>
        </div>
      </nav>

      <main className="wrap">
        {showLanding && (
          <LandingView
            onGoToLogin={() => setView("login")}
            onGoToSignup={() => setView("signup")}
          />
        )}
        {showDirectory && <ParentsView auth={auth} onGoToLogin={() => setView("login")} />}
        {showProfile && <ProfileView token={auth.token} />}
        {showMyBookings && <MyBookingsView token={auth.token} />}
        {showProviderBookings && (
          <ProviderBookingsView token={auth.token} onGoToProfile={() => setView("profile")} />
        )}
        {view === "login" && (
          <LoginView
            onLogin={handleLogin}
            onNeedsVerification={handleNeedsVerification}
            onGoToSignup={() => setView("signup")}
            onGoToForgot={() => setView("forgot")}
          />
        )}
        {view === "signup" && (
          <SignupView
            onNeedsVerification={handleNeedsVerification}
            onGoToLogin={() => setView("login")}
          />
        )}
        {view === "verify" && (
          <VerifyEmailView
            email={pendingEmail}
            onVerified={handleLogin}
          />
        )}
        {view === "forgot" && (
          <ForgotPasswordView onGoToLogin={() => setView("login")} />
        )}
        {showAdmin && (
          adminAuth ? (
            <AdminPanelView admin={adminAuth} onLogout={handleAdminLogout} />
          ) : (
            <AdminLoginView onLogin={handleAdminLogin} />
          )
        )}
      </main>

      <footer>
        Kinderkreis ist ein Konzept-/Projektentwurf zu Demonstrationszwecken und noch kein aktiver,
        registrierter Vermittlungsdienst.
        <div className="footer-admin-link">
          <button className="link-btn" onClick={() => setView("admin")}>
            Admin
          </button>
        </div>
      </footer>
    </>
  );
}
