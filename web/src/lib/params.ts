/**
 * Sanitises the `page` query parameter before it reaches the API.
 *
 * The API rejects a page below 1 with a 422, which the page's error
 * boundary then reported as "PARAKH's API didn't respond — check that the
 * FastAPI server is up". That message sent the reader to debug a server
 * that was working correctly and had rejected a bad URL exactly as it
 * should. Editing the page number in the address bar is an ordinary thing
 * to do, so the fix belongs here rather than in the error copy.
 */
export function pageParam(value: string | string[] | undefined): string {
  const raw = Array.isArray(value) ? value[0] : value;
  const n = Number(raw);
  return Number.isInteger(n) && n >= 1 ? String(n) : "1";
}
