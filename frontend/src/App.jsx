import { useState, useEffect } from "react";
import ParentsView from "./components/ParentsView.jsx";
import RegisterView from "./components/RegisterView.jsx";
import LoginView from "./components/LoginView.jsx";
import SignupView from "./components/SignupView.jsx";
import ForgotPasswordView from "./components/ForgotPasswordView.jsx";
import VerifyEmailView from "./components/VerifyEmailView.jsx";
import { logoutUser } from "./api.js";

const STORAGE_KEY = "kk_auth";

function loadAuth() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export default function App() {
  const [view, setView] = useState("eltern");
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
    setView("eltern");
  }

  function handleNeedsVerification(email) {
    setPendingEmail(email);
    setView("verify");
  }

  async function handleLogout() {
    if (auth) await logoutUser(auth.token).catch(() => {});
    setAuth(null);
    setView("eltern");
  }

  return (
    <>
      <nav>
        <div className="wrap">
          <div className="logo">
            <span className="logo-mark"></span>Kinderkreis
          </div>
          <div className="nav-links">
            <button
              className={`nav-btn ${view === "eltern" ? "active" : ""}`}
              onClick={() => setView("eltern")}
            >
              Für Eltern
            </button>
            <button
              className={`nav-btn ${view === "tagespflege" ? "active" : ""}`}
              onClick={() => setView("tagespflege")}
            >
              Für Tagespflegepersonen
            </button>

            {auth ? (
              <div className="nav-user">
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
        {view === "eltern" && <ParentsView />}
        {view === "tagespflege" && (
          <RegisterView onRegistered={() => setView("eltern")} />
        )}
        {view === "login" && (
          <LoginView
            onLogin={handleLogin}
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
