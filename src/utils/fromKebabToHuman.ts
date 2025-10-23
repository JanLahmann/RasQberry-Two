export function fromKebabToHuman(str: string): string {
  // Remove numeric prefixes like "00-", "01-", etc.
  let result = str.replace(/^\d+-/, "");
  result = result.replace(/-/g, " ");
  return result.charAt(0).toUpperCase() + result.slice(1).toLowerCase();
}
