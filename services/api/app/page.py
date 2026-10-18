"""Text-only test page for Slice 2 (§4.2 KICKSTART). Plain HTML + fetch; no sign-in.

Reads only the client-safe views (``GET /gaps/{id}``, ``/events``, ``/approval``).
"""

TEST_PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>CoverCall test page</title>
<style>
 body{font:16px/1.5 system-ui,sans-serif;margin:0 auto;max-width:44rem;padding:1rem;color:#111;background:#fff}
 button{font:inherit;min-height:48px;min-width:48px;margin:.25rem .25rem .25rem 0;padding:.5rem 1rem;border:2px solid #111;background:#fff;border-radius:.4rem;cursor:pointer}
 button:focus-visible{outline:3px solid #0b57d0;outline-offset:2px}
 table{border-collapse:collapse;width:100%;font-size:.9rem}td,th{border-bottom:1px solid #ccc;padding:.25rem;text-align:left;vertical-align:top}
 .banner{background:#fff4c2;border:1px solid #8a6d00;padding:.5rem;margin:.5rem 0}
 footer{margin-top:2rem;border-top:1px solid #ccc;padding-top:.5rem;font-weight:600}
</style></head><body>
<h1>CoverCall test page</h1>
<p class="banner" role="note">Demo time compression: <strong>{{TIME_SCALE}}</strong>. Reply windows and simulated reply delays are scaled by this factor.</p>
<section aria-labelledby="h-report"><h2 id="h-report">Report a gap</h2>
<button data-s="S-017" onclick="report(this.dataset.s)">Scenario: 6:02am sick call</button>
<button data-s="S-002" onclick="report(this.dataset.s)">Scenario: Nobody replies</button></section>
<section aria-labelledby="h-gap"><h2 id="h-gap">Gap</h2><div id="gap" aria-live="polite">No gap yet.</div>
<div id="approval"></div><div id="fallbacks"></div>
<button onclick="verifyChain()">Verify event chain</button> <span id="chain" aria-live="polite"></span></section>
<section aria-labelledby="h-ev"><h2 id="h-ev">Event log</h2><table><thead><tr><th>#</th><th>Event</th><th>From</th><th>To</th><th>Actor</th><th>Time</th></tr></thead><tbody id="events"></tbody></table></section>
<footer>All data is synthetic</footer>
<script>
let gapId = null;
const JSON_POST = (body) => ({method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
async function j(url, opt) { const r = await fetch(url, opt); if (!r.ok) { throw new Error(url + " -> HTTP " + r.status); } return r.json(); }
function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c])); }
async function report(s) { const g = await j("/gaps", JSON_POST({scenario_id: s})); gapId = g.gap_id; refresh(); }
async function approve(decision) {
  const a = await j("/gaps/" + gapId + "/approval");
  await j("/approvals", JSON_POST({gap_id: gapId, nonce: a.nonce, decision: decision, channel: "tap", transcript: ""}));
  refresh();
}
async function pick(o) { await j("/fallbacks", JSON_POST({gap_id: gapId, option: o})); refresh(); }
async function verifyChain() {
  if (!gapId) return;
  const r = await j("/gaps/" + gapId + "/events");
  document.getElementById("chain").textContent = r.chain.ok ? ("Chain OK (" + r.chain.events + " events)") : ("Chain BROKEN: " + r.chain.errors.join("; "));
}
async function refresh() {
  if (!gapId) return;
  const v = await j("/gaps/" + gapId); const g = v.gap;
  document.getElementById("gap").innerHTML = "<p><strong>" + esc(g.gap_id) + "</strong>: " + esc(g.outlet_name) + " " + esc(g.station) + " " + esc(g.start) + " to " + esc(g.end) + ". State: <strong>" + esc(g.state) + "</strong>" + (g.outcome ? (" (outcome: " + esc(g.outcome) + ")") : "") + (g.summary ? ("<br>" + esc(g.summary)) : "") + "</p>";
  const a = document.getElementById("approval");
  if (g.approval_pending) {
    const p = await j("/gaps/" + gapId + "/approval");
    a.innerHTML = "<p>" + esc(p.readback_text) + "</p><button data-d=\"approve\" onclick=\"approve(this.dataset.d)\">Approve</button><button data-d=\"reject\" onclick=\"approve(this.dataset.d)\">Reject</button>";
  } else { a.innerHTML = ""; }
  const f = document.getElementById("fallbacks");
  f.innerHTML = (g.state === "ESCALATED" && g.fallbacks) ? ("<p>Nobody accepted in time. Choose a fallback:</p>" + g.fallbacks.map(o => "<button data-o=\"" + esc(o) + "\" onclick=\"pick(this.dataset.o)\">" + esc(o.replace("_", " ")) + "</button>").join("")) : "";
  const ev = await j("/gaps/" + gapId + "/events");
  document.getElementById("events").innerHTML = ev.events.map(e => "<tr><td>" + e.seq + "</td><td>" + esc(e.type) + "</td><td>" + esc(e.from_state) + "</td><td>" + esc(e.to_state) + "</td><td>" + esc(e.actor) + "</td><td>" + esc(e.ts) + "</td></tr>").join("");
}
setInterval(refresh, 2000);
</script></body></html>
"""
