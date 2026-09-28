import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, setCsrf } from "./api";
afterEach(() => {
  vi.unstubAllGlobals();
  setCsrf("");
});
describe("protected API transport", () => {
  it("sends the in-memory CSRF token and same-origin cookie policy", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(new Response('{"ok":true}', { status: 200 }));
    vi.stubGlobal("fetch", fetcher);
    setCsrf("test-token");
    await expect(
      api("/members/search", "POST", { query: "Test Member" }),
    ).resolves.toEqual({ ok: true });
    const [url, options] = fetcher.mock.calls[0];
    expect(url).toBe("/api/members/search");
    expect(options.credentials).toBe("same-origin");
    expect(options.headers["X-CSRF-Token"]).toBe("test-token");
    expect(url).not.toContain("Test Member");
  });
  it("preserves authentication failures for the UI to clear the session", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response('{"detail":"login_required"}', { status: 401 }),
        ),
    );
    await expect(api("/members")).rejects.toMatchObject({
      code: "login_required",
      status: 401,
    });
  });
  it("does not pass arbitrary validation objects into operator messages", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response('{"detail":[{"input":"private"}]}', { status: 422 }),
        ),
    );
    await expect(api("/members")).rejects.toMatchObject({
      code: "unexpected",
      status: 422,
    });
  });
  it("reports connection failure without browser internals", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("network detail")),
    );
    await expect(api("/members")).rejects.toEqual(
      new ApiError("connection", 0),
    );
  });
});
