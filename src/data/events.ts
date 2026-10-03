/**
 * Settings for /workshops/ (content/workshops.md) - the one place to edit.
 *
 * EVENTS_EMAIL: the contact address for workshop requests. While it is the placeholder
 * (no "@"), the page shows no e-mail line.
 *
 * QDC_2025: photos and a video from the IBM Quantum Developer Conference, November 2025.
 * Photos go in public/events/ (src "/events/qdc-2025-1.jpg"); video is a URL. While both
 * are empty, the "At QDC 2025" block is not rendered.
 */
export const EVENTS_EMAIL = "EVENTS_EMAIL_TBD";

export const QDC_2025: { photos: { src: string; alt: string }[]; video: string } = {
  photos: [],
  video: "",
};
