import test from "node:test";
import assert from "node:assert/strict";
import {
  authorized,
  decryptJson,
  encryptJson,
  failureTransition,
  handleRequest,
  recoveryTransition,
  validatePost,
} from "../src/index.js";

test("validatePost accepts a UTC scheduled post", () => {
  assert.doesNotThrow(() => validatePost({
    id: "post-001",
    caption: "A synthetic character story",
    scheduled_at: "2026-11-08T23:00:00.000Z",
  }));
});

test("validatePost rejects local timestamps", () => {
  assert.throws(() => validatePost({
    id: "post-001",
    caption: "caption",
    scheduled_at: "2026-11-08T18:00:00-05:00",
  }), /ISO UTC/);
});

test("admin bearer authentication is exact", () => {
  assert.equal(authorized(new Request("https://example.test", {
    headers: { authorization: "Bearer correct" },
  }), "correct"), true);
  assert.equal(authorized(new Request("https://example.test", {
    headers: { authorization: "Bearer wrong" },
  }), "correct"), false);
});

test("health route is public", async () => {
  const response = await handleRequest(new Request("https://example.test/health"), {});
  assert.equal(response.status, 200);
  assert.equal((await response.json()).ok, true);
});

test("failure and recovery transitions avoid duplicate create retries", () => {
  const now = new Date("2026-11-08T23:00:00.000Z");
  assert.equal(failureTransition("create", now).status, "PUBLISH_REVIEW");
  assert.equal(recoveryTransition("create", now).status, "PUBLISH_REVIEW");
  assert.equal(failureTransition("prepare", now, 60).status, "PLANNED");
  assert.equal(failureTransition("prepare", now, 60).nextRetryAt, "2026-11-08T23:01:00.000Z");
});

test("AES-GCM token bundles round trip", async () => {
  const key = Buffer.alloc(32, 7).toString("base64");
  const value = { access_token: "example-token", expires_at: 123456 };
  const encrypted = await encryptJson(value, key);
  assert.notEqual(encrypted.includes(value.access_token), true);
  assert.deepEqual(await decryptJson(encrypted, key), value);
});
