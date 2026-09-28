export async function serverAvailable(
  request: typeof fetch = fetch,
): Promise<boolean> {
  try {
    const response = await request("/api/health", {
      signal: AbortSignal.timeout(3000),
    });
    if (!response.ok) return false;
    const body: unknown = await response.json();
    return (
      typeof body === "object" &&
      body !== null &&
      "status" in body &&
      body.status === "ok"
    );
  } catch {
    return false;
  }
}
