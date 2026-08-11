import { useState, useEffect } from "react";
import ParentsView from "./components/ParentsView.jsx";
import ProfileView from "./components/ProfileView.jsx";
import LoginView from "./components/LoginView.jsx";
import SignupView from "./components/SignupView.jsx";
import ForgotPasswordView from "./components/ForgotPasswordView.jsx";
import VerifyEmailView from "./components/VerifyEmailView.jsx";
import MyBookingsView from "./components/MyBookingsView.jsx";
import ProviderBookingsView from "./components/ProviderBookingsView.jsx";
import NotificationBell from "./components/NotificationBell.jsx";
import { logoutUser } from "./api.js";

const STORAGE_KEY = "kk_auth";
const AUTH_VIEWS = ["login", "signup", "verify", "forgot"];

function loadAuth() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export default function App() {
  const [view, setView] = useState("home");
  const [auth, setAuth] = useState(loadAuth);
  const [pendingEmail, setPendingEmail] = useState("");

  useEffect(() => {
    if (auth) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(auth));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, [auth]);

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
    setView("home");
  }

  // The directory (Für Eltern) is the default page and is always shown to
  // everyone — logged out, eltern, or tagespflege. Only the auth views and
  // the role-gated views below replace it.
  const showProfile = view === "profile" && auth?.role === "tagespflege";
  const showMyBookings = view === "bookings" && auth?.role === "eltern";
  const showProviderBookings = view === "provider-bookings" && auth?.role === "tagespflege";
  const showDirectory =
    !AUTH_VIEWS.includes(view) && !showProfile && !showMyBookings && !showProviderBookings;

  return (
    <>
      <nav>
        <div className="wrap">
          <button type="button" className="logo" onClick={() => setView("home")}>
            <span className="logo-mark"></span>Kinderkreis
          </button>
          <div className="nav-links">
            <button
              className={`nav-btn ${view === "home" ? "active" : ""}`}
              onClick={() => setView("home")}
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
      </main>

      <footer>
        Kinderkreis ist ein Konzept-/Projektentwurf zu Demonstrationszwecken und noch kein aktiver,
        registrierter Vermittlungsdienst.
      </footer>
    </>
  );
}
