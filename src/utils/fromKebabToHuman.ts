export function fromKebabToHuman(str: string): string {
  let result = str.replace(/-/g, " ");
  return result.charAt(0).toUpperCase() + result.slice(1).toLowerCase();
}
