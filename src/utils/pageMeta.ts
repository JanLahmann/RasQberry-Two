// Title and description of a content page, for <title>, the meta description
// and the social cards: the front matter's title/description when set,
// otherwise the page's first heading and its first paragraph.

const SITE_NAME = "RasQberry Two";

// The social card of every page (public/og-image.jpg)
export const OG_IMAGE = { url: "/og-image.jpg", width: 1200, height: 630, alt: "The RasQberry Two model: a 3D-printed IBM Quantum System Two" };
const MAX_DESCRIPTION = 155;

function plain(md: string): string {
  return md
    .replace(/<[^>]+>/g, "")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/\[([^\]]*)\]\((?:[^()]|\([^()]*\))*\)/g, "$1")
    .replace(/[*_`]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function shorten(text: string): string {
  if (text.length <= MAX_DESCRIPTION) return text;
  const cut = text.slice(0, MAX_DESCRIPTION - 1);
  return cut.slice(0, cut.lastIndexOf(" ")).replace(/[,;:.\s]+$/, "") + "…";
}

export function pageMeta(
  md: string,
  frontmatter: { title?: string; description?: string }
): { title: string; description?: string } {
  const body = md.replace(/^---[\s\S]*?\n---\n/, "").replace(/```[\s\S]*?```/g, "");
  const heading = body.match(/^# (.+)$/m)?.[1];
  // "<heading> | RasQberry Two", unless the heading names RasQberry already
  const title = frontmatter.title || (heading
    ? (/RasQberry/.test(heading) ? plain(heading) : `${plain(heading)} | ${SITE_NAME}`)
    : SITE_NAME);

  let description = frontmatter.description;
  if (!description) {
    // the first prose paragraph: no heading, list, table, quote, HTML, MDX comment or directive
    const paragraph = body
      .split(/\n\s*\n/)
      .map((p) => p.trim())
      .find((p) => p && !/^(#|<|\||-|\*|>|:|\{|!\[|\d+\.)/.test(p) && plain(p).length > 40);
    if (paragraph) description = shorten(plain(paragraph));
  }
  return { title, description };
}
