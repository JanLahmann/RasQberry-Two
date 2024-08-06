export function toKebabCase(text: string): string {
    return text
        .replace(/[^a-zA-Z0-9]/g, ' ')
        .replace(/\s+/g, '-')
        .toLowerCase()
        .replace(/^-|-$/g, '')
  }
  