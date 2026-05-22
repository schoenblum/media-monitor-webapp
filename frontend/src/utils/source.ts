/**
 * Derive a short source identifier from a result URL.
 *
 * Strips the scheme and a leading "www." prefix, leaving the registrable host
 * as it actually appears in the result (e.g. https://www.bbc.com/news/... →
 * "bbc.com"). We use the actual host rather than the configured outlet domain
 * so that results returned by a university-name search — which may legitimately
 * come from outlets that aren't in the user's library — still display a
 * correct source label.
 */
export function sourceHostFor(url: string): string {
  if (!url) return "";
  try {
    const u = new URL(url);
    return u.hostname.replace(/^www\./i, "");
  } catch {
    return url;
  }
}
