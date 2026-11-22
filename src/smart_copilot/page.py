import html

INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Smart Copilot — Ticket Desk</title>
<style>
  :root {
    --brand:   #4f46e5;
    --brand-h: #4338ca;
    --danger:  #dc2626;
    --high:    #ef4444;
    --medium:  #f59e0b;
    --low:     #22c55e;
    --bg:      #f8fafc;
    --surface: #ffffff;
    --border:  #e2e8f0;
    --text:    #1e293b;
    --muted:   #64748b;
    --radius:  10px;
  }
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
  }

  /* ── Top bar ── */
  header {
    background: var(--brand);
    color: #fff;
    padding: 0 2rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 56px;
    box-shadow: 0 2px 6px rgba(0,0,0,.18);
  }
  header h1 { font-size: 1.1rem; font-weight: 600; letter-spacing: .3px; }
  header .pill {
    background: rgba(255,255,255,.18);
    border-radius: 999px;
    padding: .2rem .75rem;
    font-size: .78rem;
    font-weight: 500;
  }

  /* ── Main layout ── */
  main {
    max-width: 900px;
    margin: 2rem auto;
    padding: 0 1.25rem;
    display: grid;
    grid-template-columns: 1fr;
    gap: 1.5rem;
  }
  @media (min-width: 720px) {
    main { grid-template-columns: 380px 1fr; }
  }

  /* ── Card ── */
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,.06);
  }
  .card-title {
    font-size: .7rem;
    font-weight: 700;
    letter-spacing: .08em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 1rem;
  }

  /* ── Compose form ── */
  textarea {
    width: 100%;
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: .65rem .8rem;
    font-size: .9rem;
    font-family: inherit;
    resize: vertical;
    min-height: 110px;
    transition: border-color .15s;
  }
  textarea:focus { outline: none; border-color: var(--brand); box-shadow: 0 0 0 3px rgba(79,70,229,.15); }

  .char-count {
    font-size: .72rem;
    color: var(--muted);
    text-align: right;
    margin-top: .3rem;
    margin-bottom: .75rem;
  }
  .char-count.near { color: var(--medium); }
  .char-count.full { color: var(--danger); }

  .btn {
    display: inline-flex;
    align-items: center;
    gap: .4rem;
    background: var(--brand);
    color: #fff;
    border: none;
    border-radius: 6px;
    padding: .55rem 1.25rem;
    font-size: .88rem;
    font-weight: 600;
    cursor: pointer;
    transition: background .15s, transform .1s;
    width: 100%;
    justify-content: center;
  }
  form button[type="submit"] {
    display: block;
    width: 100%;
    padding: .55rem 1.25rem;
    background: var(--brand);
    color: #fff;
    border: none;
    border-radius: 6px;
    font-size: .88rem;
    font-weight: 600;
    cursor: pointer;
    transition: background .15s, transform .1s;
  }
  form button[type="submit"]:hover { background: var(--brand-h); }
  form button[type="submit"]:active { transform: scale(.97); }
  form button[type="submit"]:disabled { opacity: .5; cursor: not-allowed; }

  .btn-danger {
    background: transparent;
    color: var(--danger);
    border: 1px solid #fecaca;
    padding: .3rem .7rem;
    font-size: .78rem;
    font-weight: 500;
    border-radius: 6px;
    cursor: pointer;
    transition: background .15s;
    width: auto;
  }
  .btn-danger:hover { background: #fef2f2; }

  .error-msg {
    color: var(--danger);
    font-size: .82rem;
    margin-top: .5rem;
    min-height: 1.1rem;
  }

  /* ── Queue panel ── */
  .queue-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1rem;
  }
  #ticket-count {
    background: var(--brand);
    color: #fff;
    border-radius: 999px;
    padding: .1rem .55rem;
    font-size: .72rem;
    font-weight: 700;
  }

  /* ── Ticket card ── */
  .ticket {
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem 1.1rem;
    margin-bottom: .85rem;
    background: var(--surface);
    transition: box-shadow .15s;
    position: relative;
  }
  .ticket:hover { box-shadow: 0 4px 12px rgba(0,0,0,.08); }

  /* urgency left-border accent */
  .ticket.urgency-high   { border-left: 4px solid var(--high); }
  .ticket.urgency-medium { border-left: 4px solid var(--medium); }
  .ticket.urgency-low    { border-left: 4px solid var(--low); }

  .ticket-top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: .5rem;
    margin-bottom: .6rem;
  }

  .badges { display: flex; flex-wrap: wrap; gap: .35rem; }
  .badge {
    display: inline-block;
    border-radius: 999px;
    padding: .18rem .6rem;
    font-size: .7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .04em;
  }
  .badge-high     { background: #fef2f2; color: #b91c1c; }
  .badge-medium   { background: #fffbeb; color: #92400e; }
  .badge-low      { background: #f0fdf4; color: #166534; }
  .badge-category { background: #eef2ff; color: #3730a3; }
  .badge-sentiment-negative { background: #fef2f2; color: #991b1b; }
  .badge-sentiment-neutral  { background: #f1f5f9; color: #475569; }
  .badge-sentiment-positive { background: #f0fdf4; color: #166534; }
  .badge-source   { background: #f0f9ff; color: #0369a1; }

  .ticket-message {
    font-size: .9rem;
    color: var(--text);
    margin-bottom: .75rem;
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-word;
  }

  /* ── Collapsible sections ── */
  details { margin-bottom: .4rem; }
  details summary {
    list-style: none;
    cursor: pointer;
    font-size: .78rem;
    font-weight: 600;
    color: var(--brand);
    padding: .35rem .5rem;
    border-radius: 4px;
    display: flex;
    align-items: center;
    gap: .4rem;
    user-select: none;
  }
  details summary::-webkit-details-marker { display: none; }
  details summary::before {
    content: "▶";
    font-size: .6rem;
    transition: transform .2s;
    display: inline-block;
  }
  details[open] summary::before { transform: rotate(90deg); }
  details summary:hover { background: #f1f5f9; }

  .detail-body {
    font-size: .84rem;
    color: #334155;
    line-height: 1.6;
    padding: .5rem .5rem .3rem;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .snippet-item {
    background: #f8fafc;
    border-left: 3px solid var(--brand);
    border-radius: 4px;
    padding: .4rem .65rem;
    margin-bottom: .35rem;
    font-size: .8rem;
    color: #475569;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .ticket-footer {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    margin-top: .6rem;
  }

  /* ── Empty state ── */
  .empty {
    text-align: center;
    padding: 2.5rem 1rem;
    color: var(--muted);
  }
  .empty svg { margin-bottom: .75rem; opacity: .4; }
  .empty p { font-size: .9rem; }

  /* ── Loading spinner ── */
  .spinner {
    display: inline-block;
    width: 18px;
    height: 18px;
    border: 2px solid rgba(255,255,255,.4);
    border-top-color: #fff;
    border-radius: 50%;
    animation: spin .6s linear infinite;
    vertical-align: middle;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>

<header>
  <h1>🎫 Smart Copilot — Ticket Desk</h1>
  <span class="pill">Agent view</span>
</header>

<main>
  <!-- Left: compose -->
  <div>
    <div class="card">
      <div class="card-title">New ticket</div>
      <form id="form">
        <textarea id="message" rows="6" maxlength="5000"
          placeholder="Paste the customer's message here…" aria-label="Customer message"></textarea>
        <div class="char-count" id="char-count">0 / 5000</div>
        <button type="submit">Submit</button>
        <div class="error-msg" id="error" role="alert" aria-live="polite"></div>
      </form>
    </div>
  </div>

  <!-- Right: queue -->
  <div>
    <div class="card">
      <div class="queue-header">
        <div class="card-title" style="margin-bottom:0">Queue</div>
        <span id="ticket-count">0</span>
      </div>
      <div id="tickets"></div>
    </div>
  </div>
</main>

<script>
const list     = document.getElementById("tickets");
const errorBox = document.getElementById("error");
const msgBox   = document.getElementById("message");
const counter  = document.getElementById("char-count");
const submitBtn = document.querySelector('form button[type="submit"]');
const tcountEl  = document.getElementById("ticket-count");

// ── Character counter ──
msgBox.addEventListener("input", () => {
  const n = msgBox.value.length;
  counter.textContent = n + " / 5000";
  counter.className = "char-count" + (n > 4800 ? " full" : n > 4000 ? " near" : "");
});

// ── Redirect helper ──
function toLoginIfRedirected(res) {
  if (res.redirected && new URL(res.url).pathname === "/login") {
    window.location = "/login"; return true;
  }
  return false;
}

// ── Badge helpers ──
function badge(text, cls) {
  const s = document.createElement("span");
  s.className = "badge " + cls;
  s.textContent = text;
  return s;
}
function urgencyBadge(u)   { return badge(u, "badge-" + u); }
function categoryBadge(c)  { return badge(c, "badge-category"); }
function sentimentBadge(s) { return badge("sentiment: " + s, "badge-sentiment-" + s); }
function sourceBadge(src)  { return badge("via " + src, "badge-source"); }

// ── Collapsible section ──
function section(label, buildBody) {
  const d = document.createElement("details");
  const s = document.createElement("summary");
  s.textContent = label;
  d.appendChild(s);
  const body = document.createElement("div");
  body.className = "detail-body";
  buildBody(body);
  d.appendChild(body);
  return d;
}

// ── Render ticket list ──
async function load() {
  const res = await fetch("/tickets");
  if (toLoginIfRedirected(res)) return;
  if (!res.ok) {
    errorBox.textContent = "Could not load tickets (" + res.status + ")";
    return;
  }
  const tickets = await res.json();
  list.replaceChildren();
  tcountEl.textContent = tickets.length;

  if (tickets.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.setAttribute("data-html",
      '<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">' +
      '<path d="M9 12h6M9 16h6M7 4H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V6a2 2 0 00-2-2h-2"/>' +
      '<rect x="7" y="2" width="10" height="4" rx="1"/>' +
      '</svg>');
    const svgNS = "http://www.w3.org/2000/svg";
    const svgEl = document.createElementNS(svgNS, "svg");
    svgEl.setAttribute("width","40"); svgEl.setAttribute("height","40");
    svgEl.setAttribute("viewBox","0 0 24 24"); svgEl.setAttribute("fill","none");
    svgEl.setAttribute("stroke","currentColor"); svgEl.setAttribute("stroke-width","1.5");
    empty.appendChild(svgEl);
    const p = document.createElement("p");
    p.textContent = "No tickets yet. Submit one to get started.";
    empty.appendChild(p);
    list.appendChild(empty);
    return;
  }

  for (const t of tickets) {
    const box = document.createElement("div");
    box.className = "ticket urgency-" + t.urgency;

    // Top row: badges + delete
    const top = document.createElement("div");
    top.className = "ticket-top";

    const badgeRow = document.createElement("div");
    badgeRow.className = "badges";
    badgeRow.appendChild(urgencyBadge(t.urgency));
    badgeRow.appendChild(categoryBadge(t.category));
    badgeRow.appendChild(sentimentBadge(t.sentiment));
    badgeRow.appendChild(sourceBadge(t.source));
    top.appendChild(badgeRow);
    box.appendChild(top);

    // Message
    const msg = document.createElement("div");
    msg.className = "ticket-message";
    msg.textContent = t.message;
    box.appendChild(msg);

    // Draft reply
    box.appendChild(section("💬 Draft reply", (body) => {
      body.textContent = t.draft_reply;
    }));

    // Recommended solution
    box.appendChild(section("🧠 Recommended solution", (body) => {
      body.textContent = t.recommended_solution;
    }));

    // Source snippets
    if (t.source_snippets && t.source_snippets.length > 0) {
      box.appendChild(section("📎 Source snippets (" + t.source_snippets.length + ")", (body) => {
        t.source_snippets.forEach((s) => {
          const item = document.createElement("div");
          item.className = "snippet-item";
          item.textContent = s;
          body.appendChild(item);
        });
      }));
    } else {
      box.appendChild(section("📎 Source snippets", (body) => {
        const em = document.createElement("em");
        em.textContent = "No source snippets available.";
        body.appendChild(em);
      }));
    }

    // Footer: delete
    const footer = document.createElement("div");
    footer.className = "ticket-footer";
    const del = document.createElement("button");
    del.className = "btn-danger";
    del.textContent = "Delete";
    del.setAttribute("aria-label", "Delete ticket");
    del.addEventListener("click", async () => {
      del.disabled = true;
      del.textContent = "Deleting…";
      const r = await fetch("/tickets/" + encodeURIComponent(t.id), { method: "DELETE" });
      if (toLoginIfRedirected(r)) return;
      errorBox.textContent = r.ok ? "" : "Could not delete (" + r.status + ")";
      await load();
    });
    footer.appendChild(del);
    box.appendChild(footer);

    list.appendChild(box);
  }
}

// ── Submit ──
document.getElementById("form").addEventListener("submit", async (event) => {
  event.preventDefault();
  submitBtn.disabled = true;
  submitBtn.textContent = "Analysing…";
  errorBox.textContent = "";

  const res = await fetch("/tickets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: msgBox.value }),
  });

  submitBtn.disabled = false;
  submitBtn.textContent = "Submit";

  if (toLoginIfRedirected(res)) return;
  if (res.status === 201) {
    msgBox.value = "";
    counter.textContent = "0 / 5000";
    counter.className = "char-count";
    errorBox.textContent = "";
  } else if (res.status === 422) {
    errorBox.textContent = "Message must be 1 to 5000 characters and not blank.";
  } else {
    errorBox.textContent = "Could not save ticket (" + res.status + ")";
  }
  await load();
});

load();
</script>
</body>
</html>
"""

LOGIN_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sign in — Smart Copilot</title>
<style>
  :root { --brand: #4f46e5; --brand-h: #4338ca; --danger: #dc2626; }
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .card {
    background: #fff;
    border-radius: 14px;
    padding: 2.5rem 2.25rem 2rem;
    width: 100%;
    max-width: 360px;
    box-shadow: 0 20px 60px rgba(0,0,0,.2);
  }
  .logo {
    text-align: center;
    margin-bottom: 1.5rem;
  }
  .logo .icon {
    font-size: 2.4rem;
    display: block;
    margin-bottom: .4rem;
  }
  .logo h1 {
    font-size: 1.15rem;
    font-weight: 700;
    color: #1e293b;
  }
  .logo p {
    font-size: .8rem;
    color: #64748b;
    margin-top: .2rem;
  }
  label {
    display: block;
    font-size: .78rem;
    font-weight: 600;
    color: #475569;
    margin-bottom: .3rem;
    margin-top: 1rem;
    text-transform: uppercase;
    letter-spacing: .05em;
  }
  input {
    display: block;
    width: 100%;
    padding: .6rem .8rem;
    border: 1px solid #e2e8f0;
    border-radius: 7px;
    font-size: .9rem;
    font-family: inherit;
    color: #1e293b;
    transition: border-color .15s, box-shadow .15s;
  }
  input:focus {
    outline: none;
    border-color: var(--brand);
    box-shadow: 0 0 0 3px rgba(79,70,229,.15);
  }
  .btn {
    display: block;
    width: 100%;
    padding: .65rem;
    background: var(--brand);
    color: #fff;
    border: none;
    border-radius: 7px;
    font-size: .9rem;
    font-weight: 600;
    cursor: pointer;
    margin-top: 1.5rem;
    transition: background .15s, transform .1s;
  }
  .btn:hover { background: var(--brand-h); }
  .btn:active { transform: scale(.98); }
  .error {
    color: var(--danger);
    font-size: .82rem;
    margin-top: .9rem;
    text-align: center;
    min-height: 1.1rem;
    font-weight: 500;
  }
</style>
</head>
<body>
<div class="card">
  <div class="logo">
    <span class="icon">🎫</span>
    <h1>Smart Copilot</h1>
    <p>Sign in to access the ticket desk</p>
  </div>
  <form method="post" action="/login">
    <label for="username">Username</label>
    <input id="username" name="username" autocomplete="username"
           placeholder="agent username" required>
    <label for="password">Password</label>
    <input id="password" type="password" name="password"
           autocomplete="current-password" placeholder="••••••••" required>
    <button class="btn" type="submit">Sign in →</button>
    <p class="error" role="alert">__ERROR__</p>
  </form>
</div>
</body>
</html>
"""


def login_page(error: str = "") -> str:
    """Return the login page. The inputs never carry a value, so nothing typed is echoed."""
    return LOGIN_HTML.replace("__ERROR__", html.escape(error))
