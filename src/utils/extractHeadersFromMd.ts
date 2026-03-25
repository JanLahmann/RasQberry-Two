export function extractHeadersFromMd(
  md: string,
  minLevel: number = 1,
  maxLevel: number = 6
): { title: string; level: number }[] {
  // Remove code blocks before extracting headers to avoid matching
  // comments inside code (e.g., bash comments like "# Comment")
  const mdWithoutCodeBlocks = md.replace(/```[\s\S]*?```/g, '');

  const regex = /^(#{1,6}) (.*)$/gm;
  const headings = [];
  let match;

  while ((match = regex.exec(mdWithoutCodeBlocks)) !== null) {
    const level = match[1].length;
    const title = match[2].trim();
    if (level >= minLevel && level <= maxLevel) {
      headings.push({ title, level });
    }
  }

  return headings;
}
