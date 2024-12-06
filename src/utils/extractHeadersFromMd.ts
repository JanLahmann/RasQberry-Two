export function extractHeadersFromMd(
  md: string,
  minLevel: number = 2,
  maxLevel: number = 6
): { title: string; level: number }[] {
  const regex = /^(#{1,6}) (.*)$/gm;
  const headings = [];
  let match;

  while ((match = regex.exec(md)) !== null) {
    const level = match[1].length;
    const title = match[2].trim();
    if (level >= minLevel && level <= maxLevel) {
      headings.push({ title, level });
    }
  }

  return headings;
}
