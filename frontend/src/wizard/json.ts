/** Parses user-entered JSON properties. Empty text means "no properties"; anything but an object is rejected. */
export function parseJsonObject(text: string): Record<string, unknown> | undefined {
  if (text.trim() === "") return {};
  try {
    const parsed: unknown = JSON.parse(text);
    return isPlainObject(parsed) ? parsed : undefined;
  } catch {
    return undefined;
  }
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
