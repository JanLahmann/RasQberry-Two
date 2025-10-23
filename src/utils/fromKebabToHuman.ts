export function fromKebabToHuman(str: string): string {
  // Remove numeric prefixes like "00-", "01-", etc.
  let result = str.replace(/^\d+-/, "");
  result = result.replace(/-/g, " ");

  // Title case each word
  result = result.split(' ')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');

  // Handle special cases for proper capitalization
  const specialCases: { [key: string]: string } = {
    '3d Model': '3D Model',
    '3d': '3D',
  };

  // Apply special case replacements
  for (const [pattern, replacement] of Object.entries(specialCases)) {
    const regex = new RegExp(pattern, 'gi');
    result = result.replace(regex, replacement);
  }

  return result;
}
