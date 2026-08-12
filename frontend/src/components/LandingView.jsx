// Marketing front door — the default view for anyone not logged in (see
// App.jsx: `view` starts on "landing" unless a session was already loaded
// from localStorage). Logged-in users skip straight to the directory
// instead; this page is never shown to them again unless they log out.
//
// Contact details below are placeholders — swap them for the real ones
// when available.
const CONTACT = {
  address: "Musterstraße 1, 10115 Berlin",
  phone: "+49 30 12345678",
  email: "kontakt@kinderkreis-demo.de",
};

const STEPS = [
  {
    title: "Angebot finden",
    text: "Filtern Sie nach Ort, Alter Ihres Kindes und Betreuungsform, um passende Tagespflegepersonen in Ihrer Nähe zu sehen.",
  },
  {
    title: "Anfrage stellen",
    text: "Senden Sie eine Buchungsanfrage direkt aus dem Profil — mit Wunschtermin, Adresse und einer kurzen Nachricht.",
  },
  {
    title: "Bestätigung erhalten",
    text: "Die Tagespflegeperson bestätigt oder lehnt ab. Bei einer Bestätigung erhalten beide Seiten einen Kalendereintrag per E-Mail.",
  },
];

export default function LandingView({ onGoToLogin, onGoToSignup, onBrowseDirectory }) {
  return (
    <div className="landing">
      <section className="landing-hero">
        <span className="eyebrow">Kinderkreis</span>
        <h1>Vertrauensvolle Kindertagespflege — einfach gefunden.</h1>
        <p>
          Kinderkreis verbindet Eltern mit geprüften Tagespflegepersonen und Großtagespflegestellen —
          mit klaren Qualifikationsangaben, freien Plätzen auf einen Blick und einer direkten
          Buchungsanfrage ohne Umwege.
        </p>
        <div className="landing-cta">
          <button className="btn-primary" onClick={onGoToSignup}>
            Jetzt registrieren
          </button>
          <button className="btn-ghost" onClick={onGoToLogin}>
            Anmelden
          </button>
        </div>
        <button className="link-btn landing-browse" onClick={onBrowseDirectory}>
          Oder direkt Betreuungsangebote ansehen →
        </button>
      </section>

      <section className="landing-section">
        <div className="section-head">
          <span className="eyebrow">So funktioniert's</span>
          <h1>In drei Schritten zur Betreuung</h1>
        </div>
        <div className="landing-steps">
          {STEPS.map((step, i) => (
            <div className="step-card" key={step.title}>
              <span className="step-number">{i + 1}</span>
              <h3>{step.title}</h3>
              <p>{step.text}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="landing-section">
        <div className="section-head">
          <span className="eyebrow">Warum Kinderkreis</span>
          <h1>Qualifikation, die nachvollziehbar ist</h1>
        </div>
        <div className="landing-steps">
          <div className="step-card">
            <span className="step-icon">🎓</span>
            <h3>QHB-Qualifikation sichtbar</h3>
            <p>Absolvierte Unterrichtseinheiten und Praktikumsstunden stehen direkt im Profil — keine Blackbox.</p>
          </div>
          <div className="step-card">
            <span className="step-icon">✓</span>
            <h3>Geprüfte Zertifikate</h3>
            <p>
              Hochgeladene Qualifikationsnachweise werden von unserem Team geprüft; ein bestätigtes Profil trägt
              das Prüf-Häkchen „✓ Geprüft".
            </p>
          </div>
          <div className="step-card">
            <span className="step-icon">🏠</span>
            <h3>Kindertagespflege & Großtagespflege</h3>
            <p>Ob allein betreute Kindertagespflege oder Großtagespflege mit mehreren Fachkräften — beides im Verzeichnis.</p>
          </div>
        </div>
      </section>

      <section className="landing-section landing-contact-section">
        <div className="section-head">
          <span className="eyebrow">Kontakt</span>
          <h1>Fragen? Sprechen Sie uns an.</h1>
        </div>
        <div className="contact-list landing-contact">
          <a className="contact-item" href={`mailto:${CONTACT.email}`}>
            <span className="contact-icon">✉️</span> {CONTACT.email}
          </a>
          <a className="contact-item" href={`tel:${CONTACT.phone.replace(/\s+/g, "")}`}>
            <span className="contact-icon">📞</span> {CONTACT.phone}
          </a>
          <span className="contact-item">
            <span className="contact-icon">📍</span> {CONTACT.address}
          </span>
        </div>
      </section>
    </div>
  );
}
