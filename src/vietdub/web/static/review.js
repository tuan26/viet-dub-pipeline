// Review editor: plays lines, previews voices, sends only what changed.
(function () {
  const cfg = JSON.parse(document.getElementById("review-data").textContent);
  const orig = document.getElementById("orig"), dub = document.getElementById("dub");
  const statusBox = document.getElementById("status"), dirtyLabel = document.getElementById("dirty");
  const rows = Array.from(document.querySelectorAll("#lines tr[data-index]"));
  const castRows = () => Array.from(document.querySelectorAll("#cast tr[data-speaker]"));
  let stopAt = null, stopEl = null, player = null;

  function show(msg, kind) {
    statusBox.hidden = false; statusBox.className = "flash " + (kind || "ok"); statusBox.textContent = msg;
  }
  function playRange(el, start, end) {
    [orig, dub].forEach(v => v && v.pause());
    if (player) player.pause();
    el.currentTime = Math.max(0, start - 0.15); stopAt = end + 0.3; stopEl = el; el.play();
  }
  [orig, dub].forEach(el => el && el.addEventListener("timeupdate", () => {
    if (stopEl === el && stopAt !== null && el.currentTime >= stopAt) { el.pause(); stopAt = null; }
  }));
  function playUrl(url) { if (player) player.pause(); [orig, dub].forEach(v => v && v.pause()); player = new Audio(url); player.play(); }

  async function post(url, body) {
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF": cfg.csrf, "Accept": "application/json" }, body: JSON.stringify(body) });
    const data = await r.json().catch(() => ({ error: "Máy chủ trả lời không hợp lệ (" + r.status + ")." }));
    if (!r.ok || data.error) throw new Error(data.error || ("Lỗi " + r.status));
    return data;
  }
  function voiceOf(speaker) {
    const row = castRows().find(r => r.dataset.speaker === speaker);
    return row ? row.querySelector("select.voice").value : null;
  }
  async function preview(text, voice, btn) {
    if (!text.trim()) { show("Câu trống, không có gì để đọc.", "error"); return; }
    const label = btn.textContent; btn.disabled = true; btn.textContent = "…";
    try { playUrl((await post("/review/preview", { id: cfg.id, text, voice })).url); }
    catch (e) { show(e.message, "error"); }
    finally { btn.disabled = false; btn.textContent = label; }
  }

  // remember what the page started with, to send only changes
  rows.forEach(r => {
    const sel = r.querySelector("select.speaker"), tr = r.querySelector("textarea.tr"), skip = r.querySelector("input.skip");
    r._start = { speaker: sel ? sel.value : null, tr: tr.value, skip: skip.checked };
  });
  castRows().forEach(r => r._voice = r.querySelector("select.voice").value);

  function changes() {
    const lines = [];
    rows.forEach(r => {
      const sel = r.querySelector("select.speaker"), tr = r.querySelector("textarea.tr"), skip = r.querySelector("input.skip");
      const e = { index: Number(r.dataset.index) };
      if (skip.checked !== r._start.skip || (!skip.checked && tr.value !== r._start.tr)) { if (skip.checked) e.skip = true; else e.translation = tr.value; }
      if (sel && sel.value !== r._start.speaker) e.speaker = sel.value;
      if (Object.keys(e).length > 1) lines.push(e);
      r.classList.toggle("dirty", Object.keys(e).length > 1);
    });
    const cast = {}; let voiceChanged = 0;
    castRows().forEach(r => { const v = r.querySelector("select.voice").value; cast[r.dataset.speaker] = v; if (v !== r._voice) voiceChanged++; });
    if (dirtyLabel) dirtyLabel.textContent = (lines.length || voiceChanged) ? `${lines.length} câu, ${voiceChanged} giọng chưa lưu` : "";
    return { lines, cast, pending: lines.length + voiceChanged };
  }

  function addSpeaker(name) {
    document.querySelectorAll("select.speaker").forEach(s => {
      const o = document.createElement("option"); o.textContent = name; s.insertBefore(o, s.querySelector('option[value="__new__"]'));
    });
    const table = document.getElementById("cast");
    if (!table) return;
    const tr = document.createElement("tr"); tr.dataset.speaker = name;
    const options = cfg.voices.map(v => `<option value="${v.id}">${v.label}</option>`).join("");
    tr.innerHTML = `<td><b></b></td><td class="lines">0</td><td class="muted">(nhân vật mới)</td><td></td><td><select class="voice">${options}</select></td><td><button type="button" class="voice-test">🔊 Nghe thử</button></td><td class="muted">chưa</td>`;
    tr.querySelector("b").textContent = name; tr._voice = null;
    table.appendChild(tr); bindCast(tr);
  }

  rows.forEach(r => {
    const start = Number(r.dataset.start), end = Number(r.dataset.end);
    r.querySelector(".seek").addEventListener("click", () => { orig.currentTime = start; dub.currentTime = start; });
    r.querySelector(".p-orig").addEventListener("click", () => playRange(orig, start, end));
    r.querySelector(".p-dub").addEventListener("click", () => playRange(dub, start, end));
    const test = r.querySelector(".p-test");
    if (test) test.addEventListener("click", () => {
      const sel = r.querySelector("select.speaker");
      preview(r.querySelector("textarea.tr").value, sel ? voiceOf(sel.value) : null, test);
    });
    const sel = r.querySelector("select.speaker");
    if (sel) sel.addEventListener("change", () => {
      if (sel.value === "__new__") {
        const name = (prompt("Tên người nói mới (1–30 ký tự):") || "").trim();
        if (name && /^[\w .\-]{1,30}$/u.test(name)) { addSpeaker(name); sel.value = name; }
        else { sel.value = r._start.speaker; if (name) show("Tên không hợp lệ.", "error"); }
      }
      changes();
    });
    r.querySelector("textarea.tr").addEventListener("input", changes);
    r.querySelector("input.skip").addEventListener("change", e => { r.classList.toggle("skipped", e.target.checked); changes(); });
  });
  function bindCast(r) {
    r.querySelector("select.voice").addEventListener("change", changes);
    const b = r.querySelector(".voice-test");
    if (b) b.addEventListener("click", () => {
      const line = rows.find(x => { const s = x.querySelector("select.speaker"); return s && s.value === r.dataset.speaker && !x.querySelector("input.skip").checked; });
      preview(line ? line.querySelector("textarea.tr").value : "Xin chào, đây là giọng đọc thử.", r.querySelector("select.voice").value, b);
    });
  }
  castRows().forEach(bindCast);
  document.querySelectorAll("[data-play-orig]").forEach(b => b.addEventListener("click", () => playRange(orig, Number(b.dataset.playOrig), Number(b.dataset.end))));
  const only = document.getElementById("only-flagged");
  if (only) only.addEventListener("change", () => rows.forEach(r => r.hidden = only.checked && !r.classList.contains("flagged") && !r.classList.contains("dirty")));

  async function save(then) {
    const c = changes();
    const buttons = document.querySelectorAll("#save, #save-render"); buttons.forEach(b => b.disabled = true);
    try {
      const confirm = document.getElementById("confirm-speakers");
      const res = await post("/review/save", { id: cfg.id, lines: c.lines, cast: c.cast, then, confirm_speakers: !!(confirm && confirm.checked) });
      show(res.message, "ok");
      rows.forEach(r => { const sel = r.querySelector("select.speaker"); r._start = { speaker: sel ? sel.value : null, tr: r.querySelector("textarea.tr").value, skip: r.querySelector("input.skip").checked }; });
      castRows().forEach(r => r._voice = r.querySelector("select.voice").value);
      changes();
      if (then === "rerender") setTimeout(() => location.href = "/video?id=" + encodeURIComponent(cfg.id), 1500);
    } catch (e) { show(e.message, "error"); }
    finally { buttons.forEach(b => b.disabled = false); }
  }
  const s1 = document.getElementById("save"), s2 = document.getElementById("save-render");
  if (s1) s1.addEventListener("click", () => save(null));
  if (s2) s2.addEventListener("click", () => save("rerender"));
  window.addEventListener("beforeunload", e => { if (cfg.canEdit && changes().pending) { e.preventDefault(); e.returnValue = ""; } });
})();
