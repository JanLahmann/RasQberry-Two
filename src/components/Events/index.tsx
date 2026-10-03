import { EVENTS_EMAIL, QDC_2025 } from "@/data/events";

/** "Or e-mail ..." - renders nothing until EVENTS_EMAIL is a real address. */
export function EventsEmail() {
  if (!EVENTS_EMAIL.includes("@")) return null;
  return <p>Or e-mail <a href={`mailto:${EVENTS_EMAIL}`}>{EVENTS_EMAIL}</a>.</p>;
}

/** "At QDC 2025" photos and video link - renders nothing until QDC_2025 is filled in. */
export function Qdc2025() {
  const { photos, video } = QDC_2025;
  if (photos.length === 0 && !video) return null;
  return (
    <div className="centered-media">
      {photos.length > 0 && (
        <div className="media-grid">
          {photos.map((p) => <img key={p.src} src={p.src} alt={p.alt} className="media-image" loading="lazy" />)}
        </div>
      )}
      <p className="media-caption">
        At QDC 2025{video && <> · <a href={video} target="_blank" rel="noopener">watch the video ↗</a></>}
      </p>
    </div>
  );
}
