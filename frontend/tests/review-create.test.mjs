import assert from "node:assert/strict";
import { afterEach, beforeEach, describe, it } from "node:test";

import { api } from "../src/api/http.ts";
import { createReview } from "../src/api/review.ts";
import { generateUuid } from "../src/utils/uuid.ts";

const UUID_V4_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const originalAdapter = api.defaults.adapter;
const originalCrypto = Object.getOwnPropertyDescriptor(globalThis, "crypto");
const originalLocalStorage = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
let requestConfig;

beforeEach(() => {
  requestConfig = undefined;
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: { getItem: () => null, removeItem: () => undefined }
  });
  Object.defineProperty(globalThis, "crypto", {
    configurable: true,
    value: {
      getRandomValues(target) {
        for (let index = 0; index < target.length; index += 1) target[index] = index + 1;
        return target;
      }
    }
  });
  api.defaults.adapter = async (config) => {
    requestConfig = config;
    return {
      data: { id: 42, status: "PROCESSING" },
      status: 201,
      statusText: "Created",
      headers: {},
      config
    };
  };
});

afterEach(() => {
  api.defaults.adapter = originalAdapter;
  if (originalCrypto) Object.defineProperty(globalThis, "crypto", originalCrypto);
  else delete globalThis.crypto;
  if (originalLocalStorage) Object.defineProperty(globalThis, "localStorage", originalLocalStorage);
  else delete globalThis.localStorage;
});

describe("createReview", () => {
  it("continues to POST /review/create with Idempotency-Key in the HTTP fallback path", async () => {
    const payload = { upload_id: "upload-123", scene_id: 7, scale: "标准", position: "甲方" };
    const idempotencyKey = generateUuid();

    await createReview(payload, idempotencyKey);

    assert.match(idempotencyKey, UUID_V4_PATTERN);
    assert.equal(requestConfig?.method, "post");
    assert.equal(requestConfig?.url, "/review/create");
    assert.deepEqual(JSON.parse(requestConfig?.data), payload);
    assert.equal(requestConfig?.headers.get("Idempotency-Key"), idempotencyKey);
  });
});
