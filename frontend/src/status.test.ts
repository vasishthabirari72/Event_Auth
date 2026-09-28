import { describe, expect, it, vi } from "vitest";
import { serverAvailable } from "./status";
describe("server availability", () => {
  it("rejects errors and unexpected responses", async () => {
    expect(await serverAvailable(vi.fn().mockRejectedValue(new Error()))).toBe(
      false,
    );
    expect(
      await serverAvailable(
        vi.fn().mockResolvedValue(new Response("{}", { status: 503 })),
      ),
    ).toBe(false);
    expect(
      await serverAvailable(
        vi.fn().mockResolvedValue(new Response('{"status":"wrong"}')),
      ),
    ).toBe(false);
  });
  it("accepts the local health response", async () => {
    expect(
      await serverAvailable(
        vi.fn().mockResolvedValue(new Response('{"status":"ok"}')),
      ),
    ).toBe(true);
  });
});
