const JSON_HEADERS = { "content-type": "application/json; charset=utf-8" };

export default {
  async fetch(request, env, ctx) {
    return handleRequest(request, env, ctx);
  },
  async scheduled(_controller, env, ctx) {
    ctx.waitUntil(publishDue(env));
  },
};

export async function handleRequest(request, env) {
  const url = new URL(request.url);
  if (request.method === "GET" && url.pathname === "/health") {
    return json({ ok: true, service: "ai-character-publisher" });
  }
  if (!url.pathname.startsWith("/admin/")) return json({ error: "not found" }, 404);
  if (!authorized(request, env.ADMIN_TOKEN)) return json({ error: "unauthorized" }, 401);

  try {
    if (request.method === "POST" && url.pathname === "/admin/posts") {
      const payload = await request.json();
      const posts = Array.isArray(payload.posts) ? payload.posts : [];
      if (!posts.length) throw new Error("posts must be a non-empty array");
      for (const post of posts) await upsertPost(env, post);
      return json({ ok: true, count: posts.length });
    }
    if (request.method === "POST" && url.pathname === "/admin/run") {
      return json(await publishDue(env));
    }
    if (request.method === "GET" && url.pathname === "/admin/status") {
      const rows = await env.DB.prepare(
        "SELECT id, scheduled_at, status, publish_attempts, last_error FROM posts ORDER BY scheduled_at DESC LIMIT 100",
      ).all();
      return json({ ok: true, posts: rows.results || [] });
    }
  } catch (error) {
    return json({ error: errorMessage(error) }, 400);
  }
  return json({ error: "not found" }, 404);
}

export function authorized(request, expectedToken) {
  const header = request.headers.get("authorization") || "";
  return Boolean(expectedToken) && header === `Bearer ${expectedToken}`;
}

export function validatePost(post) {
  if (!post || typeof post !== "object") throw new Error("invalid post");
  if (!/^[A-Za-z0-9_.:-]{1,120}$/.test(String(post.id || ""))) throw new Error("invalid post id");
  if (!post.caption || typeof post.caption !== "string" || post.caption.length > 280) {
    throw new Error("caption must be 1-280 characters");
  }
  const scheduled = new Date(post.scheduled_at);
  if (Number.isNaN(scheduled.getTime()) || !String(post.scheduled_at).endsWith("Z")) {
    throw new Error("scheduled_at must be an ISO UTC timestamp");
  }
}

async function upsertPost(env, post) {
  validatePost(post);
  const now = new Date().toISOString();
  await env.DB.prepare(
    `INSERT INTO posts (id, scheduled_at, caption, status, created_at, updated_at)
     VALUES (?, ?, ?, 'PLANNED', ?, ?)
     ON CONFLICT(id) DO UPDATE SET
       scheduled_at=CASE WHEN posts.status='POSTED' THEN posts.scheduled_at ELSE excluded.scheduled_at END,
       caption=CASE WHEN posts.status='POSTED' THEN posts.caption ELSE excluded.caption END,
       updated_at=excluded.updated_at`,
  ).bind(post.id, post.scheduled_at, post.caption.trim(), now, now).run();
}

export async function publishDue(env, now = new Date(), publishFn = publishToPlatform) {
  await recoverStalePosting(env, now);
  const maxLateness = Number(env.MAX_LATENESS_MINUTES || 180);
  const nowIso = now.toISOString();
  const lowerBound = new Date(now.getTime() - maxLateness * 60_000).toISOString();

  await env.DB.prepare(
    `UPDATE posts SET status='MISSED', last_error=?, updated_at=?
     WHERE status='PLANNED' AND scheduled_at < ?`,
  ).bind(`Exceeded ${maxLateness} minute publishing window`, nowIso, lowerBound).run();

  const due = await env.DB.prepare(
    `SELECT * FROM posts
     WHERE status='PLANNED' AND scheduled_at <= ? AND scheduled_at >= ?
       AND (next_retry_at='' OR next_retry_at <= ?)
     ORDER BY scheduled_at ASC LIMIT 10`,
  ).bind(nowIso, lowerBound, nowIso).all();

  const results = [];
  for (const post of due.results || []) {
    results.push(await publishOne(env, post, now, publishFn));
  }
  return { ok: true, checked_at: nowIso, due: results.length, results };
}

async function publishOne(env, post, now, publishFn) {
  const nowIso = now.toISOString();
  const claim = await env.DB.prepare(
    `UPDATE posts SET status='POSTING', posting_phase='prepare',
       publish_attempts=publish_attempts+1, last_attempt_at=?, updated_at=?, last_error=''
     WHERE id=? AND status='PLANNED'`,
  ).bind(nowIso, nowIso, post.id).run();
  if (!claim.meta || claim.meta.changes !== 1) return { id: post.id, status: "skipped" };

  let phase = "prepare";
  try {
    phase = "create";
    await setPhase(env, post.id, phase);
    const created = await publishFn(env, post);
    await env.DB.prepare(
      `UPDATE posts SET status='POSTED', posting_phase='', platform_post_id=?,
       next_retry_at='', last_error='', updated_at=? WHERE id=?`,
    ).bind(String(created.id), nowIso, post.id).run();
    return { id: post.id, status: "POSTED", platform_post_id: String(created.id) };
  } catch (error) {
    const transition = failureTransition(phase, now, Number(env.RETRY_DELAY_SECONDS || 900));
    await env.DB.prepare(
      `UPDATE posts SET status=?, posting_phase=?, next_retry_at=?, last_error=?, updated_at=? WHERE id=?`,
    ).bind(
      transition.status,
      transition.postingPhase,
      transition.nextRetryAt,
      errorMessage(error),
      nowIso,
      post.id,
    ).run();
    return { id: post.id, status: transition.status, error: errorMessage(error) };
  }
}

export function failureTransition(phase, now, retryDelaySeconds = 900) {
  if (phase === "create") {
    return { status: "PUBLISH_REVIEW", postingPhase: "create", nextRetryAt: "" };
  }
  return {
    status: "PLANNED",
    postingPhase: "",
    nextRetryAt: new Date(now.getTime() + retryDelaySeconds * 1000).toISOString(),
  };
}

export function recoveryTransition(phase, now) {
  if (phase === "create") {
    return { status: "PUBLISH_REVIEW", postingPhase: "create", nextRetryAt: "" };
  }
  return { status: "PLANNED", postingPhase: "", nextRetryAt: now.toISOString() };
}

async function recoverStalePosting(env, now) {
  const cutoff = new Date(now.getTime() - 15 * 60_000).toISOString();
  const nowIso = now.toISOString();
  await env.DB.prepare(
    `UPDATE posts SET status='PUBLISH_REVIEW', last_error='Stale create phase; verify before retrying', updated_at=?
     WHERE status='POSTING' AND posting_phase='create' AND last_attempt_at < ?`,
  ).bind(nowIso, cutoff).run();
  await env.DB.prepare(
    `UPDATE posts SET status='PLANNED', posting_phase='', next_retry_at=?,
       last_error='Recovered stale pre-create attempt', updated_at=?
     WHERE status='POSTING' AND posting_phase!='create' AND last_attempt_at < ?`,
  ).bind(nowIso, nowIso, cutoff).run();
}

async function setPhase(env, id, phase) {
  await env.DB.prepare("UPDATE posts SET posting_phase=?, updated_at=? WHERE id=?")
    .bind(phase, new Date().toISOString(), id).run();
}

async function publishToPlatform(env, post) {
  if (!env.PUBLISH_API_URL) throw new Error("PUBLISH_API_URL is not configured");
  const token = await readOAuthToken(env);
  const response = await fetch(env.PUBLISH_API_URL, {
    method: "POST",
    headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
    body: JSON.stringify({ text: post.caption, made_with_ai: true }),
  });
  if (!response.ok) throw new Error(`publishing API returned HTTP ${response.status}`);
  const payload = await response.json();
  if (!payload.id) throw new Error("publishing API returned no post id");
  return payload;
}

async function readOAuthToken(env) {
  const row = await env.DB.prepare("SELECT encrypted_json FROM oauth_state WHERE id=1").first();
  if (!row) throw new Error("OAuth is not configured");
  const bundle = await decryptJson(row.encrypted_json, env.TOKEN_ENCRYPTION_KEY);
  if (!bundle.access_token) throw new Error("OAuth access token is missing");
  return bundle.access_token;
}

export async function encryptJson(value, keyText) {
  const key = await encryptionKey(keyText, ["encrypt"]);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const plaintext = new TextEncoder().encode(JSON.stringify(value));
  const ciphertext = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, plaintext));
  return `${bytesToBase64(iv)}.${bytesToBase64(ciphertext)}`;
}

export async function decryptJson(value, keyText) {
  const [ivText, encryptedText] = String(value).split(".");
  if (!ivText || !encryptedText) throw new Error("invalid encrypted OAuth state");
  const key = await encryptionKey(keyText, ["decrypt"]);
  const plaintext = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: base64ToBytes(ivText) },
    key,
    base64ToBytes(encryptedText),
  );
  return JSON.parse(new TextDecoder().decode(plaintext));
}

async function encryptionKey(keyText, usages) {
  const raw = base64ToBytes(keyText || "");
  if (raw.byteLength !== 32) throw new Error("TOKEN_ENCRYPTION_KEY must decode to 32 bytes");
  return crypto.subtle.importKey("raw", raw, "AES-GCM", false, usages);
}

function bytesToBase64(bytes) {
  let binary = "";
  for (const value of bytes) binary += String.fromCharCode(value);
  return btoa(binary);
}

function base64ToBytes(text) {
  const binary = atob(text);
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

function json(payload, status = 200) {
  return new Response(JSON.stringify(payload), { status, headers: JSON_HEADERS });
}

function errorMessage(error) {
  return error instanceof Error ? error.message.slice(0, 1200) : String(error).slice(0, 1200);
}
