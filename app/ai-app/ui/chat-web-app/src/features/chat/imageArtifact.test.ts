// imageArtifact.test.ts
import { describe, it, expect } from "vitest";
import { resolveResourceRn } from "../chatController/chatBase";

describe("resolveResourceRn", () => {
  it("prefers rn, falls back to web_resource_rn", () => {
    expect(resolveResourceRn({ filename: "a", rn: "RN1", timestamp: 0 } as any)).toBe("RN1");
    expect(resolveResourceRn({ filename: "a", rn: "", web_resource_rn: "RN2", timestamp: 0 } as any)).toBe("RN2");
    expect(resolveResourceRn({ filename: "a", rn: "", timestamp: 0 } as any)).toBe("");
  });
});
