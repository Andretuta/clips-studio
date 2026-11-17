/** URLs may carry OAuth codes: validate without ever logging their value. */
export function safeHttps(url: unknown): url is string {
  if (typeof url !== 'string') return false
  try {
    const parsed = new URL(url)
    return parsed.protocol === 'https:' && !parsed.username && !parsed.password && !parsed.port
  } catch {
    return false
  }
}
