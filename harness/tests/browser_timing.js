"use strict";
try {
  const requested = "2026-11-16T00:01:10.000-06:00", responded = "2026-11-16T00:01:12.500-06:00";
  const check = (condition, text) => { if (!condition) throw new Error(text); };
  const send = (type, data, time = responded) => event({type, data, time});
  const request = {kind: "agent", accounting: {parts: {}, total: 1, total_exact: true}};
  const text = "\u0ba4\u0bae\u0bbf\u0bb4\u0bcd";
  send("user_message", {text: "hello"}, requested);
  send("model_request", request);
  send("assistant_delta", {kind: "agent", text});
  send("model_response", {kind: "agent", elapsed_seconds: 2.5, timings: {predicted_ms: 1250},
    usage: {completion_tokens_details: {reasoning_tokens: 42}}});
  send("assistant_message", {role: "assistant", content: text});
  send("task_complete", {summary: "done"});
  const assertConversation = () => {
    const nodes = [...document.querySelectorAll(".message")];
    check(nodes.length === 3, "Streaming answer must not be duplicated");
    check(nodes[0].querySelector("time").dateTime === requested, "Request timestamp");
    check(nodes[1].querySelector("time").dateTime === responded, "Final response timestamp");
    for (const node of nodes.slice(1)) {
      check(node.textContent.includes("2.50s total response"), "Response elapsed time");
      check(node.textContent.includes("1.25s generation"), "Server generation time");
      check(node.textContent.includes("42 reasoning tokens"), "Reported reasoning-token count");
    }
    check(nodes[1].textContent.includes(text), "Streamed Unicode");
  };
  assertConversation();
  const recorded = [...events];
  api("/api/defaults").then(defaults => {
    loadSession({id: "browser-test", config: defaults, status: "completed", events: recorded, transcript: [
      {role: "user", content: "hello"}, {role: "assistant", content: text},
      {role: "tool", content: JSON.stringify({complete: true, summary: "done"})}
    ]});
    assertConversation();
    send("model_request", request);
    send("model_response", {kind: "agent", elapsed_seconds: 0});
    send("assistant_message", {role: "assistant", content: "Non-streamed answer"});
    const last = document.querySelector(".message:last-child");
    check(last.textContent.includes("0.00s total response"), "Zero duration is valid");
    check(!last.textContent.includes("generation") && !last.textContent.includes("reasoning tokens"), "Do not invent missing server metrics");
    for (const recordedEvents of [[], [{type: "assistant_message", time: null, data: {content: "Old transcript"}}]]) {
      loadSession({id: "legacy", config: defaults, status: "answered", events: recordedEvents,
        transcript: [{role: "assistant", content: "Old transcript"}]});
      check(document.querySelector(".message-meta").textContent === "Timestamp unavailable", "Do not invent legacy timestamps");
    }
    send("run_started", {config: defaults, remaining_seconds: 90});
    check($("run_clock").textContent.includes("90s budget remaining"), "Show a live run budget");
    send("workflow_progress", {phase: "summarizing chunk", covered_bytes: 50, total_bytes: 100,
      chunks: 1, active_notes: 1, iterations: 2, max_iterations: 10});
    check($("workflow_progress").textContent.includes("50.0%"), "Show document coverage");
    send("model_request", {...request, kind: "document_chunk"});
    send("reasoning_delta", {kind: "document_chunk", text: "model supplied reasoning"});
    check(!$("model_reasoning").hidden && $("reasoning_text").textContent === "model supplied reasoning", "Show actual model reasoning separately");
    check(!events.some(item => item.type === "reasoning_delta"), "Do not retain reasoning delta fragments");
    send("model_progress", {kind: "document_chunk", elapsed_seconds: 2, content_characters: 0,
      reasoning_characters: 24, tool_characters: 0, prompt_progress: {total: 100, processed: 75, cache: 10}});
    check($("model_progress").textContent.includes("75/100"), "Show server prompt processing");
    check($("model_progress").textContent.includes("not token counts"), "Do not mislabel character counts");
    send("model_response", {kind: "document_merge", elapsed_seconds: 115.8, finish_reason: "length",
      usage: {completion_tokens: 4000, completion_tokens_details: {reasoning_tokens: 0}}});
    check($("activity").lastChild.textContent.includes("finish length"), "Expose output-limit finish reason");
    check($("activity").lastChild.textContent.includes("server output 4000 tokens (reasoning 0)"), "Use actual reported token counts");
    check($("usage").textContent.includes('"finish_reason": "length"'), "Retain finish reason in accounting");
    send("tool_result", {name: "view", tokens: 10, result: {start_offset: 0, next_offset: 12, total_bytes: 20,
      more_available: true, content_clipped: false}});
    check($("activity").lastChild.textContent.includes("MORE PAGES"), "Distinguish remaining pages");
    check(!$("activity").lastChild.textContent.includes("CLIPPED"), "Do not claim intact content was clipped");
    send("run_paused", {message: "Budget exhausted", status: "paused"});
    send("run_finished", {status: "paused"});
    check($("status").textContent === "paused" && runTimer === null, "Pause clears the live timer");
    loadSession({id: "paused", config: defaults, status: "paused", events: [],
      history: [{role: "user", content: "same objective"}], transcript: []});
    check(!$("resume").disabled, "Resume is available without a new user prompt");
    send("model_request", {...request, kind: "document_final"});
    send("assistant_delta", {kind: "document_final", text: "partial attempt"});
    send("document_retry", {kind: "document_final", previous_output_tokens: 1024, next_output_tokens: 1024,
      previous_batch_size: 1, next_batch_size: 1});
    check(document.querySelector(".message strong").textContent.includes("incomplete"), "Label truncated synthesis as incomplete");
    check($("activity").lastChild.textContent.includes("partial output not committed"), "Expose bounded retry");
    send("model_request", {...request, kind: "document_final"});
    send("assistant_delta", {kind: "document_final", text: "complete synthesis"});
    send("assistant_message", {role: "assistant", content: "complete synthesis"});
    const messages = [...document.querySelectorAll(".message")];
    check(messages.length === 2, "Keep retry output separate from incomplete output");
    check(messages[1].querySelector("span").textContent === "complete synthesis", "Do not concatenate failed and completed attempts");
    document.body.dataset.browserCheck = "passed";
  }).catch(error => { document.body.dataset.browserCheck = error.stack; });
} catch (error) { document.body.dataset.browserCheck = error.stack; }
