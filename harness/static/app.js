"use strict";
const $ = id => document.getElementById(id);
let config, session = null, events = [], inspection = null, streamingNode = null, running = false, responseMetadata = null;
const tools = ["view", "grep", "glob", "edit", "task_complete"];
const numeric = ["context", "max_input", "max_output", "max_iterations", "max_seconds", "repeat_limit",
  "temperature", "top_p", "recent_groups", "summary_tokens", "read_bytes", "scan_files", "scan_depth"];
const strings = ["base_url", "model", "working_root", "system_prompt", "completion_criteria",
  "reduction", "capture_directory"];

async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)
  });
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || `HTTP ${response.status}`);
  return value;
}
function showError(error) { $("error").textContent = error.message; }
function action(id, callback) {
  $(id).onclick = async () => { $("error").textContent = ""; try { await callback(); } catch (error) { showError(error); } };
}
function form(value) {
  config = value;
  for (const key of [...numeric, ...strings]) $(key).value = value[key];
  $("seed").value = value.seed ?? "";
  $("explicit_completion").checked = value.explicit_completion;
  $("capture_enabled").checked = value.capture;
  $("limits").value = JSON.stringify(value.limits, null, 2);
  $("tools").replaceChildren();
  for (const name of tools) {
    const label = document.createElement("label"), input = document.createElement("input");
    label.className = "inline"; input.type = "checkbox"; input.id = `tool_${name}`;
    input.checked = value.tools.includes(name); label.append(input, document.createTextNode(name));
    $("tools").append(label);
  }
  captureIndicator(value.capture);
}
function readForm() {
  const value = {...config};
  for (const key of strings) value[key] = $(key).value;
  for (const key of numeric) value[key] = Number($(key).value);
  value.seed = $("seed").value === "" ? null : Number($("seed").value);
  value.tools = tools.filter(name => $(`tool_${name}`).checked);
  value.limits = JSON.parse($("limits").value);
  value.capture = $("capture_enabled").checked;
  value.explicit_completion = $("explicit_completion").checked;
  return value;
}
function captureIndicator(enabled) {
  $("capture").textContent = enabled ? "RAW CAPTURE ON — SENSITIVE" : "CAPTURE OFF";
  $("capture").className = enabled ? "on" : "";
}
function messageMetadata(body, metadata = {}) {
  const node = body.parentElement.querySelector(".message-meta");
  node.replaceChildren();
  const time = new Date(typeof metadata.time === "string" ? metadata.time : NaN);
  if (!Number.isNaN(time.getTime())) {
    const stamp = document.createElement("time");
    stamp.dateTime = metadata.time; stamp.title = metadata.time; stamp.textContent = time.toLocaleString();
    node.append(stamp);
  } else node.append(document.createTextNode("Timestamp unavailable"));
  const seconds = value => typeof value === "number" && Number.isFinite(value) && value >= 0;
  if (seconds(metadata.elapsed_seconds)) node.append(document.createTextNode(` | ${metadata.elapsed_seconds.toFixed(2)}s total response`));
  if (seconds(metadata.timings?.predicted_ms)) node.append(document.createTextNode(` | ${(metadata.timings.predicted_ms / 1000).toFixed(2)}s generation`));
  const reasoning = metadata.usage?.completion_tokens_details?.reasoning_tokens;
  if (Number.isInteger(reasoning) && reasoning >= 0) node.append(document.createTextNode(` | ${reasoning} reasoning tokens`));
}
function message(role, text, metadata = {}) {
  const node = document.createElement("div"), title = document.createElement("strong"), body = document.createElement("span");
  const details = document.createElement("small");
  node.className = `message ${role}`; title.textContent = role; body.textContent = text;
  details.className = "message-meta"; node.append(title, details, body); messageMetadata(body, metadata);
  $("conversation").append(node);
  $("conversation").scrollTop = $("conversation").scrollHeight;
  return body;
}
function accounting(value) {
  if (!value) return;
  $("accounting").replaceChildren();
  const rows = {physical_server_context: value.physical_context ?? "unknown", session_context: value.context,
    maximum_input: value.max_input, maximum_output: value.max_output, ...value.parts,
    template_boundary_delta: value.framing_and_boundary_delta, total_input: value.total, free_input: value.remaining};
  for (const [key, number] of Object.entries(rows)) {
    const tr = document.createElement("tr"), name = document.createElement("td"), count = document.createElement("td");
    name.textContent = key.replaceAll("_", " "); count.textContent = number; tr.append(name, count); $("accounting").append(tr);
  }
  $("accuracy").textContent = `${value.total_exact ? "Rendered input: tokenizer-exact" : "TOTAL IS AN ESTIMATE"}; ` +
    `${value.component_tokenizer_exact ? "components use tokenizer" : "components estimate UTF-8 bytes / 3"}. ${value.note || ""}`;
}
function inspector() {
  const select = $("inspector_select"), previous = select.value;
  select.replaceChildren(new Option("Current assembled request / prompt / schema costs", "current"));
  for (let i = 0; i < events.length; i++) {
    if (events[i].type !== "assistant_delta") select.add(new Option(`${i}: ${events[i].type}`, String(i)));
  }
  select.value = [...select.options].some(option => option.value === previous) ? previous : "current";
  inspectSelected();
}
function inspectSelected() {
  const value = $("inspector_select").value;
  $("inspector").textContent = JSON.stringify(value === "current" ? inspection : events[Number(value)], null, 2);
}
$("inspector_select").onchange = inspectSelected;
function event(event, replay = false) {
  events.push(event);
  const data = event.data || {};
  if (event.type === "assistant_delta") {
    if (data.kind === "agent" && !replay) {
      if (!streamingNode) streamingNode = message("assistant · streaming", "", {time: event.time});
      streamingNode.textContent += data.text;
    }
    return;
  }
  if (event.type === "user_message" && !replay) message("user", data.text, {time: event.time});
  if (event.type === "assistant_message" && !replay) {
    if (!streamingNode && data.content) message("assistant", data.content, responseMetadata || {time: event.time});
    if (streamingNode) streamingNode.parentElement.querySelector("strong").textContent = "assistant";
    streamingNode = null;
  }
  if (event.type === "task_complete" && !replay) message("task complete", data.summary, {...responseMetadata, time: event.time});
  if (event.type === "run_started") { captureIndicator(data.config.capture); responseMetadata = null; }
  if (event.type === "model_request") {
    accounting(data.accounting);
    if (data.kind === "agent") responseMetadata = null;
  }
  if (event.type === "context_reduction") accounting(data.after);
  if (event.type === "model_response") {
    if (data.kind === "agent") {
      responseMetadata = {...data, time: event.time};
      if (streamingNode && !replay) messageMetadata(streamingNode, responseMetadata);
    }
    $("usage").textContent = JSON.stringify({
      server_usage: data.usage, discrepancy: data.input_discrepancy,
      elapsed_seconds: data.elapsed_seconds, server_timings: data.timings
    }, null, 2);
  }
  if (event.type === "run_error" || event.type === "http_error") $("error").textContent = data.message;
  if (event.type === "run_finished") $("status").textContent = data.status;
  if (!["raw_response", "assistant_message", "user_message"].includes(event.type)) {
    const li = document.createElement("li");
    let detail = "";
    if (event.type === "tool_call") detail = `${data.name} ${JSON.stringify(data.arguments)}`;
    else if (event.type === "tool_result") detail = `${data.name}: ${data.result.returned ?? "—"}/${data.result.total ?? "?"} returned; ` +
      `${data.tokens} ${data.tokenizer_exact ? "tokens" : "estimated tokens"}; ${data.elapsed_seconds.toFixed(3)}s` +
      (data.result.truncated ? "; TRUNCATED" : "") + (data.result.error ? `; ${data.result.error}` : "");
    else if (event.type === "context_reduction") detail = `${data.before.total} → ${data.after.total} tokens; ${data.policy}`;
    else if (event.type === "run_error") detail = data.message;
    else if (event.type === "model_request") detail = `${data.kind}; ${data.accounting.total} input ${data.accounting.total_exact ? "tokens" : "estimated tokens"}`;
    else if (event.type === "task_complete") detail = data.summary;
    li.textContent = `${new Date(event.time || Date.now()).toLocaleTimeString()} ${event.type}\n${detail}`;
    $("activity").append(li);
  }
  if (!replay) inspector();
}
async function refresh() {
  inspection = await api(`/api/sessions/${session.id}/inspect`, {});
  accounting(inspection.accounting); inspector();
}
function loadSession(value) {
  session = value; form(value.config); events = []; streamingNode = null; responseMetadata = null;
  $("conversation").replaceChildren(); $("activity").replaceChildren();
  const timeline = [];
  let response = null, cursor = 0;
  for (const item of value.events) {
    if (item.type === "model_response" && item.data.kind === "agent") response = {...item.data, time: item.time};
    if (["run_started", "model_request"].includes(item.type) && item.data.kind !== "summary") response = null;
    if (item.type === "user_message") timeline.push({role: "user", text: item.data.text, metadata: {time: item.time}});
    if (item.type === "assistant_message" && item.data.content) timeline.push({role: "assistant", text: item.data.content, metadata: response || {time: item.time}});
    if (item.type === "task_complete") timeline.push({role: "task complete", text: item.data.summary, metadata: {...response, time: item.time}});
  }
  const restore = (role, text) => {
    const item = timeline[cursor];
    const matches = item?.role === role && item.text === text;
    if (matches) cursor++;
    message(role, text, matches ? item.metadata : {});
  };
  for (const item of value.transcript) {
    if (["user", "assistant"].includes(item.role) && item.content) restore(item.role, item.content);
    if (item.role === "tool") {
      const result = JSON.parse(item.content);
      if (result.complete) restore("task complete", result.summary);
    }
  }
  for (const item of value.events) event(item, true);
  $("status").textContent = value.status; inspector();
}
function setRunning(value) {
  running = value;
  for (const id of ["send", "create", "apply", "load", "measure", "save"]) $(id).disabled = value;
  $("stop").disabled = !value;
}
action("create", async () => { loadSession(await api("/api/sessions", {config: readForm()})); await refresh(); });
action("apply", async () => {
  if (!session) throw new Error("Create a session first.");
  loadSession(await api(`/api/sessions/${session.id}/config`, readForm())); await refresh();
});
action("measure", async () => { if (!session) throw new Error("Create a session first."); await refresh(); });
action("send", async () => {
  if (!session) throw new Error("Create a session first.");
  if (JSON.stringify(readForm()) !== JSON.stringify(session.config)) throw new Error("Apply the configuration changes before sending.");
  const prompt = $("prompt").value; if (!prompt.trim()) return;
  setRunning(true); streamingNode = null; $("status").textContent = "running"; $("prompt").value = "";
  let finished = false;
  try {
    const response = await fetch(`/api/sessions/${session.id}/run`, {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({prompt})
    });
    if (!response.ok) throw new Error((await response.json()).error);
    const reader = response.body.getReader(), decoder = new TextDecoder("utf-8", {fatal: true});
    let buffer = "";
    while (true) {
      const {value, done} = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), {stream: !done});
      let end;
      while ((end = buffer.indexOf("\n\n")) !== -1) {
        const packet = buffer.slice(0, end); buffer = buffer.slice(end + 2);
        if (packet.startsWith("data: ")) {
          const item = JSON.parse(packet.slice(6)); event(item);
          if (item.type === "run_finished") finished = true;
        }
      }
      if (done) break;
    }
    if (!finished) throw new Error("Event stream ended before run_finished; inspect server terminal.");
    session = await api(`/api/sessions/${session.id}`);
    await refresh();
  } finally { setRunning(false); }
});
action("stop", async () => { if (session) await api(`/api/sessions/${session.id}/stop`, {}); });
action("save", async () => {
  if (!session) throw new Error("Create a session first.");
  const value = await api(`/api/sessions/${session.id}`), blob = new Blob([JSON.stringify(value, null, 2)], {type: "application/json;charset=utf-8"});
  const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = `session-${session.id}.json`;
  link.click(); setTimeout(() => URL.revokeObjectURL(link.href), 1000);
});
action("load", async () => $("import_file").click());
$("import_file").onchange = async () => {
  try {
    const file = $("import_file").files[0]; if (!file) return;
    loadSession(await api("/api/import", JSON.parse(await file.text()))); await refresh();
  } catch (error) { showError(error); } finally { $("import_file").value = ""; }
};
for (const name of ["context", "max_output"]) $(name).onchange = () => {
  $("max_input").value = Number($("context").value) - Number($("max_output").value);
};
setRunning(false);
api("/api/defaults").then(form).catch(showError);
