import { EVENTS_EMAIL, QDC_2025 } from "@/data/events";
import { UMAMI, umamiAttrs } from "@/lib/umami";

/** "Or e-mail ..." - renders nothing until EVENTS_EMAIL is a real address. */
export function EventsEmail() {
  if (!EVENTS_EMAIL.includes("@")) return null;
  return <p>Or e-mail <a href={`mailto:${EVENTS_EMAIL}`} {...umamiAttrs(UMAMI.workshopContact, { via: "email" })}>{EVENTS_EMAIL}</a>.</p>;
}

/** Photos and the clip from the conference as one grid - renders nothing until QDC_2025 is filled in. */
export function Qdc2025() {
  const { photos, video } = QDC_2025;
  if (photos.length === 0 && !video) return null;
  return (
    <div className="centered-media">
      <div className="event-grid">
        {photos.map((p) => <img key={p.src} src={p.src} alt={p.alt} loading="lazy" />)}
        {video && (
          <video src={video} autoPlay muted loop playsInline controls preload="metadata"
                 aria-label="Opening the RasQberry Two model at the IBM Quantum Developer Conference 2025" />
        )}
      </div>
      <p className="media-caption">At the IBM Quantum Developer Conference 2025</p>
    </div>
  );
}
