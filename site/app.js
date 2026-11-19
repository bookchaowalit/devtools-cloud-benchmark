// Cloud Benchmark Lab page: reads data.json and shows the latest passing run per target as a card,
// or an empty state that says how runs start and which targets are planned.
(function () {
  const REPO = "https://github.com/bookchaowalit/devtools-cloud-benchmark";
  const PLANNED = [
    ["Railway", "ADR-0003-railway.md"],
    ["Render", "ADR-0004-render.md"],
    ["Fly.io", "ADR-0005-fly.md"],
    ["Google Cloud Run", "ADR-0006-cloud-run.md"],
  ];
  const el = (tag, attrs = {}, text) => { const n = document.createElement(tag); Object.assign(n, attrs); if (text !== undefined) n.textContent = text; return n; };
  const fmt = (v, d = 0) => (v === null || v === undefined ? "—" : Number(v).toFixed(d));
  const day = (iso) => new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(iso));

  function stat(label, value, unit, bad) {
    const box = el("div");
    const dd = el("dd", {}, value);
    if (unit && value !== "—") dd.append(el("small", {}, unit));
    if (bad) dd.dataset.bad = "true";
    box.append(el("dt", {}, label), dd);
    return box;
  }

  function card(run) {
    const m = run.metrics || {}, spec = run.target_spec || {};
    const li = el("li", { className: "cb-target" });
    li.append(el("h3", {}, spec.provider || run.target), el("p", { className: "cb-size" }, spec.size || "Size not recorded"));
    const errors = m.load_items?.error_rate;
    const dl = el("dl", { className: "cb-stats" });
    dl.append(
      stat("Deploy", fmt(m.deploy_s, 1), "s"),
      stat("Ready", fmt(m.ready_s, 1), "s"),
      stat("Sequential p50", fmt(m.latency_sequential?.p50_ms, 1), "ms"),
      stat("Sequential p95", fmt(m.latency_sequential?.p95_ms, 1), "ms"),
      stat("Load requests/s", fmt(m.load_items?.rps_median), ""),
      stat("Load p95", fmt(m.load_items?.p95_ms, 1), "ms"),
      stat("CPU requests/s", fmt(m.load_cpu?.rps_median, 1), ""),
      stat("Errors", errors === null || errors === undefined ? "—" : `${fmt(errors * 100, 2)}%`, "", Boolean(errors && errors > 0)),
    );
    const link = el("a", { className: "cb-run", href: `${REPO}/tree/main/results/${encodeURIComponent(run.id)}` }, `Run record, ${day(run.started_at)}`);
    li.append(dl, link);
    return li;
  }

  function empty(title, text, withPlan) {
    const box = el("div", { className: "rs-empty" });
    box.append(el("h3", {}, title), el("p", {}, text));
    if (withPlan) {
      const list = el("ul", { className: "cb-plan" });
      for (const [name, file] of PLANNED) {
        const li = el("li");
        li.append(el("a", { href: `${REPO}/blob/main/docs/adr/${file}` }, name), " — planned target, ADR proposed");
        list.append(li);
      }
      box.append(list);
    }
    return box;
  }

  /** Latest run per target, in the order targets first appear. */
  function latestByTarget(runs) {
    const latest = new Map();
    for (const run of runs) latest.set(run.target, run);
    return [...latest.values()];
  }

  async function start() {
    const status = document.getElementById("updated");
    const box = document.getElementById("latest");
    try {
      const res = await fetch("data.json");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const { runs } = await res.json();
      const latest = latestByTarget(runs);
      if (!latest.length) {
        status.textContent = "No published runs yet.";
        box.replaceChildren(empty("No published runs yet",
          "Runs start by hand from the bench workflow (workflow_dispatch); each one creates paid resources for a few minutes and deletes them, so a schedule waits on the owner's cost decision. A target appears here after its ADR is approved and it has a real run that passed the contract.", true));
        return;
      }
      status.textContent = `${latest.length} ${latest.length === 1 ? "target" : "targets"} · latest run ${day(runs[runs.length - 1].started_at)}`;
      const list = el("ul", { className: "cb-targets" });
      latest.forEach((run) => list.append(card(run)));
      box.replaceChildren(list);
    } catch (error) {
      status.textContent = "The results could not be loaded.";
      box.replaceChildren(empty("Could not load the results", `${error.message}. Reload the page, or read the raw records in the repository.`, false));
    }
  }

  window.CB = { latestByTarget };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
