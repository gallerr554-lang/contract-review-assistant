import assert from "node:assert/strict";
import { afterEach, describe, it } from "node:test";

import { generateUuid } from "../src/utils/uuid.ts";

const UUID_V4_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const originalCrypto = Object.getOwnPropertyDescriptor(globalThis, "crypto");

function setCrypto(value) {
  Object.defineProperty(globalThis, "crypto", { configurable: true, value });
}

afterEach(() => {
  if (originalCrypto) Object.defineProperty(globalThis, "crypto", originalCrypto);
  else delete globalThis.crypto;
});

describe("generateUuid", () => {
  it("uses crypto.randomUUID when it is available", () => {
    const expected = "9bd9e334-9816-44a5-a58e-40537d10420c";
    let fallbackCalled = false;
    setCrypto({
      randomUUID: () => expected,
      getRandomValues: () => {
        fallbackCalled = true;
        throw new Error("fallback should not be called");
      }
    });

    assert.equal(generateUuid(), expected);
    assert.equal(fallbackCalled, false);
  });

  it("uses getRandomValues when randomUUID is unavailable and returns UUID v4", () => {
    let fallbackCalls = 0;
    setCrypto({
      getRandomValues(target) {
        fallbackCalls += 1;
        target.set([0x10, 0x32, 0x54, 0x76, 0x98, 0xba, 0xfc, 0xde, 0x01, 0x23, 0x45, 0x67, 0x89, 0xab, 0xcd, 0xef]);
        return target;
      }
    });

    const uuid = generateUuid();

    assert.equal(fallbackCalls, 1);
    assert.match(uuid, UUID_V4_PATTERN);
    assert.equal(uuid, "10325476-98ba-4cde-8123-456789abcdef");
  });

  it("fails explicitly when Web Crypto is unavailable", () => {
    setCrypto(undefined);

    assert.throws(() => generateUuid(), /不支持 Web Crypto 安全随机数/);
  });
});
