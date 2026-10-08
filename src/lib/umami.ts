/**
 * Umami click events on rasqberry.org, as data-umami-event attributes (the
 * footer's pattern): Umami's script sends the event when the element is
 * clicked. Names follow the Fun with Quantum v2 scheme, "RasQberry Two: <what
 * happened>"; the Pi's own events start with the same prefix (rq_umami_event.py).
 */
export const UMAMI = {
  imagerOpen: 'RasQberry Two: imager open',
  imageDownload: 'RasQberry Two: image download',
  learningPathClick: 'RasQberry Two: learning path click',
  workshopContact: 'RasQberry Two: workshop contact',
  feedbackClick: 'RasQberry Two: feedback click',
  assistantOpen: 'RasQberry Two: assistant open',
  // Homepage "New beta" box (content/index.md), data: target (imager, release-notes, feedback, ab-image, learning-paths)
  betaBoxClick: 'RasQberry Two: beta box click',
  // Homepage on a Pi (?from=pi): the welcome's links, data: target
  piWelcomeClick: 'RasQberry Two: pi welcome click',
} as const;

/** The attributes for one event: data-umami-event plus one data-umami-event-<key> per value. */
export function umamiAttrs(event: string, data: Record<string, string> = {}): Record<string, string> {
  const attrs: Record<string, string> = { 'data-umami-event': event };
  for (const [key, value] of Object.entries(data)) attrs[`data-umami-event-${key}`] = value;
  return attrs;
}

/**
 * Markdown links that count, wherever a page has them: the demo feedback form
 * (data: the demo, from its demo= parameter) and the workshop request form.
 */
export function linkEvent(href?: string): Record<string, string> {
  if (!href) return {};
  if (href.includes('template=demo-feedback.yml')) {
    let demo = 'all';
    try {
      demo = new URL(href).searchParams.get('demo') || 'all';
    } catch {
      /* keep 'all' */
    }
    return umamiAttrs(UMAMI.feedbackClick, { demo });
  }
  if (href.includes('template=workshop-request.yml')) {
    return umamiAttrs(UMAMI.workshopContact, { via: 'request-form' });
  }
  return {};
}
