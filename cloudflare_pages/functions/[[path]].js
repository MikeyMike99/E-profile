// e-profile on Cloudflare Pages: static snapshot + live backend on the owner's PC.
//
// Every request except /static/* comes through here (see public/_routes.json).
//  - Anonymous GETs of pages that exist in the snapshot are served from it (fast, works
//    when the PC is off).
//  - Everything else (login, admin panel, projects, blog, forms, APIs) and every request
//    from a logged-in browser goes to ORIGIN_URL (DevCore, via the Cloudflare Tunnel) with
//    the X-EProfile-Proxy secret, where DevCore routes it to CyberBrief (newsletter) or
//    to the local e-profile server. If the PC is offline, GETs fall back to the snapshot
//    and the rest gets a short "offline" page.
// Pages env vars: ORIGIN_URL (https://siraugga.mikeytech.dev), ORIGIN_SECRET (secret).

const page = (title, body, status) => new Response(
  `<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>${title}</title>
<body style="font-family:system-ui;max-width:36rem;margin:15vh auto;padding:0 16px">${body}
<p><a href="/">Back to home</a></p></body></html>`,
  { status, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" } });

const offline = () => page("Temporarily offline",
  "<h1>This part is offline right now</h1><p>Sign-in and interactive features run on a private " +
  "server that is currently unavailable. The public pages still work.</p>" +
  '<p><a href="https://rescue.mikeytech.dev">Super Admin: break glass</a></p>', 503);

// Pages whose content changes often: always try live first (new stories, download counts,
// usage numbers), falling back to the snapshot when the PC is offline.
const FRESH_EXACT = ["/newsletter", "/downloads", "/usage", "/telemetry"];
const freshFirst = (p) => FRESH_EXACT.includes(p) || p.startsWith("/newsletter/story/");
// e-profile's Flask session cookie => the visitor is logged in.
const loggedIn = (req) => /(?:^|;\s*)session=/.test(req.headers.get("cookie") || "");

async function fromOrigin(request, env, url, timeoutMs, bodyOverride) {
  const origin = new URL(env.ORIGIN_URL);
  const headers = new Headers(request.headers);
  headers.set("X-Forwarded-Host", url.host);
  headers.set("X-Forwarded-Proto", "https");
  headers.set("X-EProfile-Proxy", env.ORIGIN_SECRET || "");
  const resp = await fetch(new URL(url.pathname + url.search, origin), {
    method: request.method,
    headers,
    body: ["GET", "HEAD"].includes(request.method) ? undefined : (bodyOverride ?? request.body),
    redirect: "manual",
    signal: timeoutMs ? AbortSignal.timeout(timeoutMs) : undefined,
  });
  if ([502, 503, 504, 530].includes(resp.status)) throw new Error("origin down");
  const out = new Response(resp.body, resp);
  const loc = out.headers.get("location");
  if (loc) {
    const l = new URL(loc, origin);
    if (l.host === origin.host) out.headers.set("location", l.pathname + l.search + l.hash);
  }
  return out;
}

// Echos Lab sound calibrator: the page is part of the static snapshot and its results
// go straight into Cloudflare D1 (binding DB), so it works 24/7 without the PC.
// The PC's e-profile sync downloads new rows into calibration_data.csv.
async function calibratorLog(request, env) {
  if (!env.DB) return Response.json({ status: "error", message: "Storage unavailable" }, { status: 503 });
  let d = {};
  try { d = await request.json(); } catch { d = {}; }
  const s = (v, n = 200) => (v === undefined || v === null ? "" : String(v)).slice(0, n);
  const now = Math.floor(Date.now() / 1000);
  try {
    await env.DB.prepare(
      "INSERT INTO echos_calibration (created_at, time_text, user, x, z, key, dir, comment) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
    ).bind(now, new Date((now + 7200) * 1000).toISOString().replace("T", " ").slice(0, 19),
           s(d.u, 100), s(d.x, 40), s(d.z, 40), s(d.k, 40), s(d.d, 40), s(d.c, 1000)).run();
    return Response.json({ status: "ok" });
  } catch {
    return Response.json({ status: "error", message: "Failed to write data" }, { status: 500 });
  }
}

// JOSHY downloads: counted in D1, then served by the latest GitHub release (always on,
// files too large for Pages). The PC's sync copies the counts into e-profile.
const GH = "https://github.com/MikeyMike99/JOSHY";
const DOWNLOADS = {
  installer: `${GH}/releases/latest/download/JOSHY-Setup.exe`,
  portable: `${GH}/releases/latest/download/JOSHY.exe`,
  git_source: `${GH}/archive/refs/heads/main.zip`,
};

async function download(request, env, pkg) {
  const target = DOWNLOADS[pkg];
  if (!target) return Response.redirect(new URL("/downloads", request.url), 302);
  if (env.DB) {
    try {
      const ua = (request.headers.get("user-agent") || "").slice(0, 120);
      const ip = request.headers.get("cf-connecting-ip") || "";
      const day = new Date().toISOString().slice(0, 10);
      const hash = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",
        new TextEncoder().encode(`${ip}-${ua.slice(0, 40)}-${day}`)))).slice(0, 4)
        .map((b) => b.toString(16).padStart(2, "0")).join("");
      await env.DB.prepare("INSERT INTO joshy_downloads (created_at, package_id, client_hash, user_agent) VALUES (?, ?, ?, ?)")
        .bind(Math.floor(Date.now() / 1000), pkg, hash, ua).run();
    } catch { /* never block a download on counting */ }
  }
  return new Response(null, { status: 302, headers: { location: target, "cache-control": "no-store" } });
}

// Newsletter subscribe / unsubscribe: the PC (CyberBrief) answers when it is on. When it
// is offline the request is stored in D1 and CyberBrief applies it (and sends the welcome
// email) as soon as it is back, so signing up and unsubscribing always work.
const SUBSCRIBE_PATHS = ["/api/newsletter/subscribe", "/api/subscribe", "/subscribe"];

async function parseBody(request, raw) {
  const type = request.headers.get("content-type") || "";
  const text = new TextDecoder().decode(raw);
  if (type.includes("application/json")) { try { return JSON.parse(text || "{}"); } catch { return {}; } }
  return Object.fromEntries(new URLSearchParams(text));
}

async function queueNewsletter(env, action, payload) {
  if (!env.DB) throw new Error("no storage");
  await env.DB.prepare("INSERT INTO newsletter_queue (created_at, action, payload) VALUES (?, ?, ?)")
    .bind(Math.floor(Date.now() / 1000), action, JSON.stringify(payload).slice(0, 8000)).run();
}

async function newsletterWithFallback(request, env, url) {
  const raw = request.method === "GET" ? new ArrayBuffer(0) : await request.arrayBuffer();
  if (env.ORIGIN_URL) {
    try {
      return await fromOrigin(request, env, url, 8000, raw.byteLength ? raw : undefined);
    } catch { /* PC offline: queue it */ }
  }
  const body = await parseBody(request, raw);
  const isSubscribe = SUBSCRIBE_PATHS.includes(url.pathname);
  try {
    if (isSubscribe) {
      const email = String(body.email || "").trim().toLowerCase();
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email) || email.length > 254) {
        return Response.json({ status: "error", message: "Please enter a valid email address." }, { status: 400 });
      }
      await queueNewsletter(env, "subscribe", { ...body, email });
      return Response.json({ status: "success", queued: true,
        message: `Thanks! ${email} is subscribed to Cyber Threat Intelligence. Your welcome email will arrive shortly.` });
    }
    const token = String(url.searchParams.get("token") || body.token || "").trim();
    if (!token) return Response.json({ status: "error", message: "Missing unsubscribe token." }, { status: 400 });
    const purge = ["1", "true", "yes"].includes(String(url.searchParams.get("purge") || body.purge || "").toLowerCase());
    const oneClick = body["List-Unsubscribe"] === "One-Click";
    await queueNewsletter(env, "unsubscribe", { token, purge: purge && !oneClick });
    if (request.method === "POST") return Response.json({ status: "success", queued: true, message: "You have been unsubscribed." });
    return page("Unsubscribed", "<h1>You have been unsubscribed</h1><p>You will not receive further CyberBrief emails. " +
      "It can take a few hours before this shows in your preferences.</p>", 200);
  } catch {
    return offline();
  }
}

export async function onRequest({ request, env }) {
  const url = new URL(request.url);
  const read = ["GET", "HEAD"].includes(request.method);

  if (url.pathname === "/echos-calibrator/log" && request.method === "POST") return calibratorLog(request, env);
  if (read && url.pathname.startsWith("/downloads/get/")) return download(request, env, url.pathname.slice(15));
  if ((request.method === "POST" && SUBSCRIBE_PATHS.includes(url.pathname)) ||
      (url.pathname === "/newsletter/unsubscribe" && (request.method === "POST" || url.searchParams.get("token")))) {
    return newsletterWithFallback(request, env, url);
  }
  if (read && (url.pathname === "/echos-calibrator" || url.pathname === "/echos-calibrator/")) {
    return env.ASSETS.fetch(new Request(new URL("/echos-calibrator", url), request));
  }

  if (url.pathname.startsWith("/admin/notify")) {
    return page("Newsletter admin moved",
      '<h1>The newsletter admin has moved</h1><p>CyberBrief is managed from Siraugga: ' +
      '<a href="https://siraugga.mikeytech.dev/admin/notify">open the CyberBrief admin</a>.</p>', 200);
  }

  if (read) {
    const snapshot = await env.ASSETS.fetch(request);
    const hasSnapshot = snapshot.status === 200;
    if (hasSnapshot && !freshFirst(url.pathname) && !loggedIn(request)) return snapshot;
    if (env.ORIGIN_URL) {
      try {
        return await fromOrigin(request, env, url, hasSnapshot ? 6000 : 0);
      } catch { /* PC offline */ }
    }
    return hasSnapshot ? snapshot : offline();
  }

  if (!env.ORIGIN_URL) return offline();
  try {
    return await fromOrigin(request, env, url, 0);
  } catch {
    return offline();
  }
}
