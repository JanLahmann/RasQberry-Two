// Words a folder or file name cannot spell: "04-jans-corner" is "Jan's Corner",
// "led-display" is "LED Display", "03-ab-boot" is "A/B Boot".
const specialWords: { [key: string]: string } = {
  '3d': '3D',
  'ab': 'A/B',
  'jans': "Jan's",
  'led': 'LED',
  'leds': 'LEDs',
};

// Small words stay lower case inside a title ("Bill of Materials")
const smallWords = new Set(['a', 'an', 'and', 'for', 'in', 'of', 'on', 'or', 'the', 'to']);

export function fromKebabToHuman(str: string): string {
  // Remove numeric prefixes like "00-", "01-", etc.
  const words = str.replace(/^\d+-/, "").split('-').filter(Boolean);

  // Title case each word, with the special words and small words above
  return words
    .map((word, i) => {
      const lower = word.toLowerCase();
      if (specialWords[lower]) return specialWords[lower];
      if (i > 0 && smallWords.has(lower)) return lower;
      return lower.charAt(0).toUpperCase() + lower.slice(1);
    })
    .join(' ');
}
