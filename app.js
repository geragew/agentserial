const examples = {
  overspend: {
    run: "0042", title: "Parallel Payment Agents", verdict: "FAILED", timestamp: "2026-08-31 21:14:08",
    metrics: ["02", "08", "01", "00", "04 ops"],
    invariant: "total_spend <= 1000", observed: "1600", allowed: "1000", difference: "+600",
    reason: "Both agents derived their actions from <code>budget@v41</code> before either effect became visible to the other.",
    resource: "budget", version: "v41", ordering: "NO CONTRACT-VALID ORDERING FOUND",
    contract: `version: "0.1"

resources:
  budget:
    initial: 1000
  spends:
    initial: []

invariants:
  - id: spending-limit
    type: max_sum
    resource: spends
    max: 1000`,
    rawContract: `{"version":"0.1","invariants":[{"id":"spending-limit","type":"max_sum","resource":"spends","max":1000}]}`,
    lanes: [
      { agent: "AGENT_A", id: "payment-a", events: [{ left: 4, type: "read", label: "READ", value: "budget=1000@v41", op: "op-a-read" }, { left: 54, type: "effect", label: "EFFECT", value: "spend +800", op: "op-a-spend" }] },
      { agent: "AGENT_B", id: "payment-b", events: [{ left: 20, type: "read", label: "READ", value: "budget=1000@v41", op: "op-b-read" }, { left: 68, type: "effect", label: "EFFECT", value: "spend +800", op: "op-b-spend" }] }
    ],
    history: [
      row("14:21:00.910", "system", "INIT", "budget", "1000", "v41", "—", "OK", "op-init-budget"),
      row("14:21:00.914", "system", "INIT", "spends", "[]", "v0", "—", "OK", "op-init-spends"),
      row("14:21:01.129", "agent-a", "READ", "budget", "1000", "v41", "—", "OK", "op-a-read"),
      row("14:21:01.144", "agent-b", "READ", "budget", "1000", "v41", "—", "OK", "op-b-read"),
      row("14:21:01.608", "agent-a", "DECIDE", "spends", "—", "—", "+800", "OK", "op-a-decide"),
      row("14:21:01.731", "agent-b", "DECIDE", "spends", "—", "—", "+800", "OK", "op-b-decide"),
      row("14:21:02.102", "agent-a", "EFFECT", "spends", "—", "v1", "+800", "OK", "op-a-spend"),
      row("14:21:02.338", "agent-b", "EFFECT", "spends", "—", "v2", "+800", "OK", "op-b-spend")
    ],
    counter: [
      counter("AGENT_A", "READ", "budget", "1000", "version 41", "op-a-read"),
      counter("AGENT_B", "READ", "budget", "1000", "version 41", "op-b-read"),
      counter("AGENT_A", "EFFECT", "spend", "+800", "commit v1", "op-a-spend"),
      counter("AGENT_B", "EFFECT", "spend", "+800", "commit v2", "op-b-spend")
    ]
  },
  booking: {
    run: "0043", title: "Concurrent Seat Reservation", verdict: "FAILED", timestamp: "2026-08-31 21:18:22",
    metrics: ["02", "06", "01", "00", "04 ops"], invariant: "unique(reserved_seats)", observed: "A12 × 2", allowed: "A12 × 1", difference: "+1",
    reason: "Both reservation agents committed <code>seat:A12</code>. The unique-resource contract rejects every feasible ordering.", resource: "seat:A12", version: "v7", ordering: "NO CONTRACT-VALID ORDERING FOUND",
    contract: `version: "0.1"

resources:
  reserved_seats:
    initial: []

invariants:
  - id: one-reservation-per-seat
    type: unique
    resource: reserved_seats`,
    rawContract: `{"version":"0.1","invariants":[{"id":"one-reservation-per-seat","type":"unique","resource":"reserved_seats"}]}`,
    lanes: [
      { agent: "AGENT_A", id: "web-checkout", events: [{ left: 6, type: "read", label: "READ", value: "A12=available@v7", op: "book-a-read" }, { left: 55, type: "effect", label: "EFFECT", value: "reserve A12", op: "book-a-write" }] },
      { agent: "AGENT_B", id: "desk-terminal", events: [{ left: 21, type: "read", label: "READ", value: "A12=available@v7", op: "book-b-read" }, { left: 69, type: "effect", label: "EFFECT", value: "reserve A12", op: "book-b-write" }] }
    ],
    history: [row("14:31:10.000","system","INIT","seat:A12","available","v7","—","OK","book-init"),row("14:31:10.121","agent-a","READ","seat:A12","available","v7","—","OK","book-a-read"),row("14:31:10.147","agent-b","READ","seat:A12","available","v7","—","OK","book-b-read"),row("14:31:10.710","agent-a","DECIDE","seat:A12","—","—","reserve","OK","book-a-decide"),row("14:31:11.102","agent-a","EFFECT","seat:A12","—","v8","reserve","OK","book-a-write"),row("14:31:11.225","agent-b","EFFECT","seat:A12","—","v9","reserve","OK","book-b-write")],
    counter: [counter("AGENT_A","READ","seat:A12","available","version 7","book-a-read"),counter("AGENT_B","READ","seat:A12","available","version 7","book-b-read"),counter("AGENT_A","EFFECT","reservation","A12","commit v8","book-a-write"),counter("AGENT_B","EFFECT","reservation","A12","commit v9","book-b-write")]
  },
  inventory: {
    run: "0044", title: "Last-Unit Inventory Race", verdict: "INVALID HISTORY", timestamp: "2026-08-31 21:22:51",
    metrics: ["02", "06", "01", "00", "04 ops"], invariant: "inventory >= 0", observed: "stale read", allowed: "current version", difference: "v0 → v1",
    reason: "The second purchase cannot reproduce its recorded read after the first decrement. No replay explains both observations.", resource: "inventory", version: "v0", ordering: "NO FEASIBLE REPLAY FOUND",
    contract: `version: "0.1"

resources:
  inventory:
    initial: 1

invariants:
  - id: non-negative-stock
    type: min_value
    resource: inventory
    min: 0`,
    rawContract: `{"version":"0.1","invariants":[{"id":"non-negative-stock","type":"min_value","resource":"inventory","min":0}]}`,
    lanes: [
      { agent: "AGENT_A", id: "storefront-a", events: [{ left: 5, type: "read", label: "READ", value: "inventory=1@v0", op: "inv-a-read" }, { left: 53, type: "effect", label: "EFFECT", value: "inventory -1", op: "inv-a-write" }] },
      { agent: "AGENT_B", id: "storefront-b", events: [{ left: 18, type: "read", label: "READ", value: "inventory=1@v0", op: "inv-b-read" }, { left: 68, type: "effect", label: "EFFECT", value: "inventory -1", op: "inv-b-write" }] }
    ],
    history: [row("14:40:01.000","system","INIT","inventory","1","v0","—","OK","inv-init"),row("14:40:01.129","agent-a","READ","inventory","1","v0","—","OK","inv-a-read"),row("14:40:01.144","agent-b","READ","inventory","1","v0","—","OK","inv-b-read"),row("14:40:02.102","agent-a","EFFECT","inventory","—","v1","-1","OK","inv-a-write"),row("14:40:02.338","agent-b","EFFECT","inventory","—","v2","-1","OK","inv-b-write"),row("14:40:02.500","system","CHECK","inventory","-1","v2","—","OK","inv-check")],
    counter: [counter("AGENT_A","READ","inventory","1","version 0","inv-a-read"),counter("AGENT_B","READ","inventory","1","version 0","inv-b-read"),counter("AGENT_A","EFFECT","inventory","-1","commit v1","inv-a-write"),counter("AGENT_B","EFFECT","inventory","-1","commit v2","inv-b-write")]
  },
  config: {
    run: "0045", title: "Cross-System Configuration Migration", verdict: "FAILED", timestamp: "2026-08-31 21:27:13",
    metrics: ["02", "08", "02", "00", "04 ops"], invariant: "code_revision == deploy_revision", observed: "1 != 2", allowed: "equal", difference: "+1 rev",
    reason: "Each migration is valid against the initial configuration, but their non-commutative effects produce mismatched revisions.", resource: "revision", version: "v12", ordering: "NO CONTRACT-VALID ORDERING FOUND",
    contract: `version: "0.1"

resources:
  code_revision:
    initial: 0
  deploy_revision:
    initial: 0

invariants:
  - id: matching-revisions
    type: equals
    left: code_revision
    right: deploy_revision`,
    rawContract: `{"version":"0.1","invariants":[{"id":"matching-revisions","type":"equals","left":"code_revision","right":"deploy_revision"}]}`,
    lanes: [
      { agent: "AGENT_A", id: "code-migrator", events: [{ left: 7, type: "read", label: "READ", value: "revisions=0/0", op: "cfg-a-read" }, { left: 52, type: "effect", label: "EFFECT", value: "code +1 / deploy=1", op: "cfg-a-write" }] },
      { agent: "AGENT_B", id: "deploy-migrator", events: [{ left: 21, type: "read", label: "READ", value: "revisions=0/0", op: "cfg-b-read" }, { left: 67, type: "effect", label: "EFFECT", value: "code=1 / deploy +1", op: "cfg-b-write" }] }
    ],
    history: [row("15:02:00.010","system","INIT","revisions","0 / 0","v12","—","OK","cfg-init"),row("15:02:01.100","agent-a","READ","revisions","0 / 0","v12","—","OK","cfg-a-read"),row("15:02:01.160","agent-b","READ","revisions","0 / 0","v12","—","OK","cfg-b-read"),row("15:02:01.600","agent-a","DECIDE","code_revision","—","—","+1","OK","cfg-a-decide"),row("15:02:01.740","agent-b","DECIDE","deploy_revision","—","—","+1","OK","cfg-b-decide"),row("15:02:02.110","agent-a","EFFECT","revisions","—","v13","1 / 1","OK","cfg-a-write"),row("15:02:02.300","agent-b","EFFECT","revisions","—","v14","1 / 2","OK","cfg-b-write"),row("15:02:02.550","system","CHECK","revisions","1 / 2","v14","—","OK","cfg-check")],
    counter: [counter("AGENT_A","READ","revisions","0 / 0","version 12","cfg-a-read"),counter("AGENT_B","READ","revisions","0 / 0","version 12","cfg-b-read"),counter("AGENT_A","EFFECT","revisions","1 / 1","commit v13","cfg-a-write"),counter("AGENT_B","EFFECT","revisions","1 / 2","commit v14","cfg-b-write")]
  }
};

function row(time, agent, operation, resource, observed, version, effect, status, id) {
  return { time, agent, operation, resource, observed, version, effect, status, id };
}
function counter(agent, kind, resource, value, version, id) { return { agent, kind, resource, value, version, id }; }

const runs = [
  ["0045", "Config mismatch", "21:27:13", "08", "02", "CONTRACT_FAIL"],
  ["0044", "Inventory race", "21:22:51", "06", "00", "INCONSISTENT_HISTORY"],
  ["0043", "Double booking", "21:18:22", "06", "02", "CONTRACT_FAIL"],
  ["0042", "Overspend", "21:14:08", "08", "02", "CONTRACT_FAIL"],
  ["0041", "Safe parallel", "21:09:40", "06", "02", "ROBUST_PASS"]
];

let currentKey = "overspend";
let currentView = "overview";
let selectedOperation = null;
let contractMode = "interpreted";
let drawerMode = "interpreted";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

function showRoute() {
  const hash = location.hash || "#home";
  const inWorkspace = hash.startsWith("#workspace");
  $("#site").hidden = inWorkspace;
  $("#workspaceView").hidden = !inWorkspace;
  if (inWorkspace) {
    const requested = hash.split("/")[1] || currentView;
    switchView($(`[data-view-panel="${requested}"]`) ? requested : "overview", false);
  }
}

function switchView(view, updateHash = true) {
  currentView = view;
  $$("[data-view-panel]").forEach(panel => panel.classList.toggle("active", panel.dataset.viewPanel === view));
  $$(".sidebar-nav [data-view]").forEach(button => button.classList.toggle("active", button.dataset.view === view));
  $("#sidebar").classList.remove("open");
  if (updateHash) location.hash = `workspace/${view}`;
}

function renderExample(key) {
  currentKey = key;
  const data = examples[key];
  $("#runId").textContent = data.run;
  $("#runTitle").textContent = data.title;
  $("#runTime").textContent = data.timestamp;
  const verdict = $("#verdict");
  verdict.textContent = data.verdict;
  verdict.className = data.verdict === "PASSED" ? "pass" : data.verdict.includes("INVALID") ? "inconclusive" : "";
  $$("#summaryStrip strong").forEach((node, index) => node.textContent = data.metrics[index]);
  $("#invariantText").textContent = data.invariant;
  $("#observedValue").textContent = data.observed;
  $("#allowedValue").textContent = data.allowed;
  $("#differenceValue").textContent = data.difference;
  $("#reasonText").innerHTML = data.reason;
  $("#orderingResult").textContent = data.ordering;
  $("#exampleSelect").value = key;
  $$(".example-link").forEach(button => button.classList.toggle("active", button.dataset.example === key));
  renderTimeline(data);
  renderHistory(data);
  renderCounterexample(data);
  renderContract(data);
  populateFilters(data);
  closeDrawer();
}

function renderTimeline(data) {
  const timeline = $("#timeline");
  timeline.innerHTML = data.lanes.map(lane => `
    <div class="timeline-lane">
      <div class="lane-label"><strong>${lane.agent}</strong><span>${lane.id}</span></div>
      <div class="lane-track">
        ${lane.events.map(event => `<button class="trace-event ${event.type}" data-operation="${event.op}" style="left:${event.left}%"><span>${event.label}</span><strong>${event.value}</strong></button>`).join("")}
        <span class="trace-success">SUCCESS</span>
      </div>
    </div>`).join("") + `
    <div class="timeline-lane global-lane"><div class="lane-label"><strong>GLOBAL</strong><span>contract</span></div><div class="lane-track"><span class="global-failure">${data.verdict === "INVALID HISTORY" ? "REPLAY INCONSISTENT" : "CONTRACT FAILURE"}</span></div></div>`;
  bindOperationClicks(timeline);
}

function renderHistory(data) {
  $("#historyBody").innerHTML = data.history.map(item => `<tr data-operation="${item.id}" data-agent="${item.agent}" data-resource="${item.resource}"><td>${item.time}</td><td>${item.agent}</td><td>${item.operation}</td><td>${item.resource}</td><td>${item.observed}</td><td>${item.version}</td><td>${item.effect}</td><td class="status-ok">${item.status}</td></tr>`).join("");
  bindOperationClicks($("#historyBody"));
}

function renderCounterexample(data) {
  $("#counterSubtitle").textContent = `${data.counter.length} operations are sufficient to reproduce this failure.`;
  $("#retainedCount").textContent = `${String(data.counter.length).padStart(2, "0")} / ${String(data.history.length).padStart(2, "0")}`;
  $("#counterPreview").innerHTML = data.counter.map((item, index) => `<button class="counter-row" data-operation="${item.id}"><span class="index">${String(index + 1).padStart(2, "0")}</span><strong>${item.agent}</strong><span class="muted">${item.kind}</span><span>${item.resource}</span><strong>${item.value}</strong></button>`).join("");
  $("#counterDetail").innerHTML = data.counter.map((item, index) => `<button class="counter-operation" data-operation="${item.id}"><span class="op-number">${String(index + 1).padStart(2, "0")}</span><div><span>AGENT</span><strong>${item.agent}</strong></div><div><span>TYPE</span><strong>${item.kind}</strong></div><div class="op-value"><span>${item.resource.toUpperCase()}</span><strong>${item.value}</strong></div><div class="op-version"><span>EVIDENCE</span><strong>${item.version}</strong></div></button>`).join("");
  bindOperationClicks($("#counterPreview"));
  bindOperationClicks($("#counterDetail"));
}

function renderContract(data) {
  const content = contractMode === "raw" ? data.rawContract : data.contract;
  $("#contractCode").textContent = content;
  $("#lineNumbers").innerHTML = content.split("\n").map(() => "<li></li>").join("");
  $("#parsedResources").textContent = data.metrics[2];
}

function populateFilters(data) {
  const agents = [...new Set(data.history.map(item => item.agent))];
  const resources = [...new Set(data.history.map(item => item.resource))];
  $("#agentFilter").innerHTML = `<option value="all">All agents</option>${agents.map(value => `<option>${value}</option>`).join("")}`;
  $("#resourceFilter").innerHTML = `<option value="all">All resources</option>${resources.map(value => `<option>${value}</option>`).join("")}`;
}

function filterHistory() {
  const agent = $("#agentFilter").value;
  const resource = $("#resourceFilter").value;
  $$("#historyBody tr").forEach(row => {
    row.hidden = (agent !== "all" && row.dataset.agent !== agent) || (resource !== "all" && row.dataset.resource !== resource);
  });
}

function bindOperationClicks(root) {
  $$('[data-operation]', root).forEach(node => node.addEventListener("click", () => openDrawer(node.dataset.operation)));
}

function findOperation(id) {
  const data = examples[currentKey];
  const history = data.history.find(item => item.id === id);
  const counterItem = data.counter.find(item => item.id === id);
  return history || (counterItem && { id, time: data.timestamp.split(" ")[1], agent: counterItem.agent.toLowerCase().replace("_", "-"), operation: counterItem.kind, resource: counterItem.resource, observed: counterItem.kind === "READ" ? counterItem.value : "—", version: counterItem.version, effect: counterItem.kind === "EFFECT" ? counterItem.value : "—", status: "OK" });
}

function openDrawer(id) {
  selectedOperation = findOperation(id);
  if (!selectedOperation) return;
  $("#drawerTitle").textContent = selectedOperation.id;
  renderDrawer();
  $("#detailDrawer").classList.add("open");
  $("#detailDrawer").setAttribute("aria-hidden", "false");
  $$('[data-operation]').forEach(node => node.classList.toggle("highlight", node.dataset.operation === id));
}

function renderDrawer() {
  if (!selectedOperation) return;
  const op = selectedOperation;
  const raw = { id: op.id, agent: op.agent, operation: op.operation.toLowerCase(), resource: op.resource, observed: op.observed, version: op.version, effect: op.effect, status: "success" };
  $("#drawerContent").innerHTML = drawerMode === "raw" ? `<div class="drawer-block"><span>RAW EVENT</span><pre>${escapeHtml(JSON.stringify(raw, null, 2))}</pre></div>` : `
    <dl class="drawer-fields"><div><dt>OPERATION ID</dt><dd>${op.id}</dd></div><div><dt>AGENT</dt><dd>${op.agent}</dd></div><div><dt>STARTED</dt><dd>${op.time}</dd></div><div><dt>COMPLETED</dt><dd>${incrementTime(op.time)}</dd></div><div><dt>STATUS</dt><dd class="status-ok">SUCCESS</dd></div><div><dt>SOURCE</dt><dd>otel://local/${op.id}</dd></div></dl>
    <div class="drawer-block"><span>READ SET</span><div class="drawer-set">${op.observed !== "—" ? `${op.resource} = ${op.observed} @ ${op.version}` : "∅"}</div></div>
    <div class="drawer-block"><span>EFFECT SET</span><div class="drawer-set">${op.effect !== "—" ? `${op.resource} ${op.effect}` : "∅"}</div></div>
    <div class="drawer-block"><span>DEPENDENCIES</span><div class="drawer-set">recorded-state → ${op.id}</div></div>`;
}

function closeDrawer() {
  $("#detailDrawer").classList.remove("open");
  $("#detailDrawer").setAttribute("aria-hidden", "true");
  $$('[data-operation]').forEach(node => node.classList.remove("highlight"));
}

function renderRuns() {
  $("#runsBody").innerHTML = runs.map(item => `<tr><td>${item[0]}</td><td>${item[1]}</td><td>${item[2]}</td><td>${item[3]}</td><td>${item[4]}</td><td class="${item[5] === "ROBUST_PASS" ? "status-ok" : "status-fail"}">${item[5]}</td></tr>`).join("");
}

function incrementTime(time) {
  if (!time || !time.includes(".")) return time;
  const [base, millis] = time.split(".");
  return `${base}.${String(Number(millis) + 37).padStart(3, "0")}`;
}
function escapeHtml(value) { return value.replace(/[&<>"]/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[char]); }

function wireInteractions() {
  window.addEventListener("hashchange", showRoute);
  $$(".sidebar-nav [data-view]").forEach(button => button.addEventListener("click", () => switchView(button.dataset.view)));
  $$('[data-go-view]').forEach(button => button.addEventListener("click", () => switchView(button.dataset.goView)));
  $$(".example-link").forEach(button => button.addEventListener("click", () => { renderExample(button.dataset.example); switchView("overview"); }));
  $("#loadExample").addEventListener("click", () => renderExample($("#exampleSelect").value));
  $("#runCheck").addEventListener("click", () => {
    document.body.classList.add("checking");
    setTimeout(() => { renderExample($("#exampleSelect").value); document.body.classList.remove("checking"); }, 650);
  });
  $("#openAnalyzer").addEventListener("click", () => $("#analyzerDialog").showModal());
  $("#closeAnalyzer").addEventListener("click", () => $("#analyzerDialog").close());
  $("#analyzerForm").addEventListener("submit", runFileAnalysis);
  $("#agentFilter").addEventListener("change", filterHistory);
  $("#resourceFilter").addEventListener("change", filterHistory);
  $$("[data-code-mode]").forEach(button => button.addEventListener("click", () => { contractMode = button.dataset.codeMode; $$("[data-code-mode]").forEach(item => item.classList.toggle("active", item === button)); renderContract(examples[currentKey]); }));
  $$("[data-drawer-mode]").forEach(button => button.addEventListener("click", () => { drawerMode = button.dataset.drawerMode; $$("[data-drawer-mode]").forEach(item => item.classList.toggle("active", item === button)); renderDrawer(); }));
  $("#closeDrawer").addEventListener("click", closeDrawer);
  $("#menuButton").addEventListener("click", () => $("#sidebar").classList.toggle("open"));
  $("#sidebarScrim").addEventListener("click", () => $("#sidebar").classList.remove("open"));
  $$('[data-theme-toggle]').forEach(button => button.addEventListener("click", toggleTheme));
  document.addEventListener("keydown", event => { if (event.key === "Escape") { closeDrawer(); $("#sidebar").classList.remove("open"); } });
}

async function runFileAnalysis(event) {
  event.preventDefault();
  const submit = $("#submitAnalysis");
  const status = $("#analyzerStatus");
  const endpoint = $("#apiEndpoint").value.replace(/\/+$/, "");
  const history = $("#historyFile").files[0];
  const contract = $("#contractFile").files[0];
  const form = new FormData();
  form.append("history", history);
  form.append("contract", contract);
  const headers = {};
  if ($("#apiKey").value) headers["X-AgentSerial-Key"] = $("#apiKey").value;
  submit.disabled = true;
  status.textContent = "Analyzing feasible execution orders…";
  $("#analyzerResult").hidden = true;
  try {
    const limit = encodeURIComponent($("#operationLimit").value);
    const response = await fetch(`${endpoint}/v1/check-files?max_operations=${limit}`, { method: "POST", headers, body: form });
    const result = await response.json();
    if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : `API returned ${response.status}`);
    $("#apiVerdict").textContent = result.status;
    $("#apiOperations").textContent = result.operations;
    $("#apiFeasible").textContent = result.feasible_replays;
    $("#apiSafe").textContent = result.safe_replays;
    $("#apiUnsafe").textContent = result.unsafe_replays;
    $("#apiCounterexample").textContent = result.reduced_counterexample?.join(" → ") || "None";
    $("#analyzerResult").dataset.verdict = result.status;
    $("#analyzerResult").hidden = false;
    status.textContent = `Analysis complete · request ${response.headers.get("X-Request-ID") || "local"}`;
  } catch (error) {
    status.textContent = `Analysis failed: ${error.message}`;
  } finally {
    submit.disabled = false;
  }
}

function toggleTheme() {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("agentserial-theme", next);
  syncThemeControls();
}

function syncThemeControls() {
  const dark = document.documentElement.dataset.theme === "dark";
  $$('[data-theme-toggle]').forEach(button => {
    button.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
    button.setAttribute("title", dark ? "Switch to light theme" : "Switch to dark theme");
  });
}

renderExample(currentKey);
renderRuns();
wireInteractions();
syncThemeControls();
showRoute();
