const state = {
  videos: [],
  q: "",
  channel: "",
  activeTags: new Set(),
  sortBy: "published_at",
  sortDir: "desc",
  expanded: new Set(),
};

async function load() {
  try {
    const r = await fetch("./videos.json", { cache: "no-store" });
    state.videos = await r.json();
  } catch (e) {
    console.error(e);
    state.videos = [];
  }
  buildFilters();
  render();
  updateMeta();
}

function buildFilters() {
  const tagSet = new Set();
  const channelSet = new Set();
  state.videos.forEach(v => {
    (v.topic_tags || []).forEach(t => tagSet.add(t));
    if (v.channel) channelSet.add(v.channel);
  });

  const tagsEl = document.getElementById("tags");
  tagsEl.innerHTML = "";
  [...tagSet].sort().forEach(t => {
    const b = document.createElement("button");
    b.className = "tag-pill";
    b.textContent = t;
    b.onclick = () => {
      state.activeTags.has(t) ? state.activeTags.delete(t) : state.activeTags.add(t);
      b.classList.toggle("active");
      render();
    };
    tagsEl.appendChild(b);
  });

  const sel = document.getElementById("channel");
  sel.innerHTML = '<option value="">(all)</option>';
  [...channelSet].sort().forEach(c => {
    const o = document.createElement("option");
    o.value = c; o.textContent = c;
    sel.appendChild(o);
  });

  document.getElementById("q").oninput = e => { state.q = e.target.value.toLowerCase(); render(); };
  sel.onchange = e => { state.channel = e.target.value; render(); };
  document.querySelectorAll("th[data-sort]").forEach(th => {
    th.onclick = () => {
      const f = th.dataset.sort;
      if (state.sortBy === f) state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
      else { state.sortBy = f; state.sortDir = "desc"; }
      render();
    };
  });
}

function filtered() {
  return state.videos.filter(v => {
    if (state.channel && v.channel !== state.channel) return false;
    if (state.activeTags.size > 0) {
      const vt = new Set(v.topic_tags || []);
      for (const t of state.activeTags) if (!vt.has(t)) return false;
    }
    if (state.q) {
      const hay = `${v.title} ${v.channel} ${v.summary}`.toLowerCase();
      if (!hay.includes(state.q)) return false;
    }
    return true;
  }).sort((a, b) => {
    const av = a[state.sortBy] || "", bv = b[state.sortBy] || "";
    const cmp = av < bv ? -1 : av > bv ? 1 : 0;
    return state.sortDir === "asc" ? cmp : -cmp;
  });
}

function render() {
  const tbody = document.getElementById("rows");
  tbody.innerHTML = "";
  const rows = filtered();
  document.getElementById("empty").classList.toggle("hidden", rows.length > 0);
  rows.forEach(v => {
    const tr = document.createElement("tr");
    tr.className = "video-row border-b border-slate-200";
    tr.innerHTML = `
      <td class="px-2 py-2 whitespace-nowrap">${(v.published_at || "").slice(0, 10)}</td>
      <td class="px-2 py-2">${escapeHtml(v.channel)}</td>
      <td class="px-2 py-2"><a class="text-indigo-700 hover:underline" href="${v.url}" target="_blank">${escapeHtml(v.title)}</a></td>
      <td class="px-2 py-2">${(v.topic_tags || []).map(t => `<span class="tag-pill">${escapeHtml(t)}</span>`).join(" ")}</td>
      <td class="px-2 py-2">${v.transcript_source}</td>
    `;
    tr.onclick = (e) => {
      if (e.target.tagName === "A") return;
      toggleDetail(tr, v);
    };
    tbody.appendChild(tr);
    if (state.expanded.has(v.video_id)) appendDetail(tr, v);
  });
}

function toggleDetail(tr, v) {
  if (state.expanded.has(v.video_id)) {
    state.expanded.delete(v.video_id);
    const next = tr.nextSibling;
    if (next && next.classList && next.classList.contains("row-detail")) next.remove();
  } else {
    state.expanded.add(v.video_id);
    appendDetail(tr, v);
  }
}

function appendDetail(tr, v) {
  const d = document.createElement("tr");
  d.className = "row-detail";
  const quotes = (v.key_quotes || []).map(q => `<li>“${escapeHtml(q)}”</li>`).join("");
  const related = (v.related_channels || []).map(c => escapeHtml(c)).join(", ");
  d.innerHTML = `
    <td colspan="5">
      <div class="mb-2"><b>Summary:</b> ${escapeHtml(v.summary)}</div>
      <div class="mb-2 text-xs text-slate-500">Transcript source: ${v.transcript_source} · ${v.transcript_excerpt_chars} chars · Related: ${related || "(none)"}</div>
      <div class="mb-2"><b>Key quotes:</b><ul class="list-disc list-inside">${quotes || "<li>(none)</li>"}</ul></div>
      <details><summary class="cursor-pointer text-indigo-700">Transcript excerpt (first 500 chars)</summary>
        <pre class="whitespace-pre-wrap text-xs mt-2 bg-white p-2 border rounded">${escapeHtml(v.transcript_excerpt || "")}</pre>
      </details>
    </td>
  `;
  tr.parentNode.insertBefore(d, tr.nextSibling);
}

function updateMeta() {
  const latest = state.videos.reduce((m, v) => v.processed_at > m ? v.processed_at : m, "");
  document.getElementById("meta").textContent =
    `${state.videos.length} videos · last refresh ${latest || "n/a"}`;
}

function escapeHtml(s) {
  return String(s || "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
}

load();
