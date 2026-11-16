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
    document.body.dataset.browserCheck = "passed";
  }).catch(error => { document.body.dataset.browserCheck = error.stack; });
} catch (error) { document.body.dataset.browserCheck = error.stack; }
