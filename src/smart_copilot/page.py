INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Ticket Desk</title>
<style>
body { font-family: sans-serif; max-width: 48rem; margin: 2rem auto; padding: 0 1rem; }
textarea { width: 100%; box-sizing: border-box; }
.ticket { border: 1px solid #ccc; border-radius: 4px; padding: 0.75rem; margin: 0.75rem 0; }
.meta { color: #444; font-size: 0.9rem; }
.error { color: #b00020; }
</style>
</head>
<body>
<h1>Ticket Desk</h1>
<form id="form">
  <label for="message">Customer message</label>
  <textarea id="message" rows="5" maxlength="5000"></textarea>
  <button type="submit">Submit</button>
  <span id="error" class="error"></span>
</form>
<h2>Tickets</h2>
<div id="tickets"></div>
<script>
const list = document.getElementById("tickets");
const errorBox = document.getElementById("error");

function line(parent, className, text) {
  const el = document.createElement("div");
  el.className = className;
  el.textContent = text;
  parent.appendChild(el);
}

async function load() {
  const res = await fetch("/tickets");
  if (!res.ok) {
    errorBox.textContent = "Could not load tickets (" + res.status + ")";
    return;
  }
  const tickets = await res.json();
  list.replaceChildren();
  if (tickets.length === 0) {
    line(list, "meta", "No tickets yet.");
    return;
  }
  for (const t of tickets) {
    const box = document.createElement("div");
    box.className = "ticket";
    line(box, "meta", "Category: " + t.category + " | Urgency: " + t.urgency +
      " | Sentiment: " + t.sentiment + " | Source: " + t.source);
    line(box, "message", t.message);
    line(box, "draft", "Draft: " + t.draft_reply);
    line(box, "recommendation", "Recommendation: " + t.recommended_solution);
    if (t.source_snippets.length > 0) {
      t.source_snippets.forEach(function(s) {
        line(box, "snippet", "Source: " + s);
      });
    } else {
      const em = document.createElement("em");
      em.textContent = "No source snippets available.";
      box.appendChild(em);
    }
    const del = document.createElement("button");
    del.textContent = "Delete";
    del.addEventListener("click", async () => {
      const r = await fetch("/tickets/" + encodeURIComponent(t.id), { method: "DELETE" });
      errorBox.textContent = r.ok ? "" : "Could not delete (" + r.status + ")";
      await load();
    });
    box.appendChild(del);
    list.appendChild(box);
  }
}

document.getElementById("form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const box = document.getElementById("message");
  const res = await fetch("/tickets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: box.value }),
  });
  if (res.status === 201) {
    box.value = "";
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
