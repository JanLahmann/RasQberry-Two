export function extractH2FromMd(md: string): string[] {
  const regex = /^(## .*)$/gm;
  let headings = [];
  let match;
  while ((match = regex.exec(md)) !== null) {
    headings.push(match[1].replace('## ', ''));
  }
  return headings;
}
