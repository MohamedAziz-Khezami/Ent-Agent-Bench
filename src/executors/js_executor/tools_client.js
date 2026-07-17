// tools_client.js — lives inside the JS executor container. `tools` is
// what generated code sees. Genuinely asynchronous — fetch() is inherently
// Promise-based in Node, so tool calls require a real `await`. Every call
// is a real HTTP request to the tool-server, reached only over the private
// per-episode Docker network (this container has no direct database access).
'use strict';

// `counter` is a mutable {count} object exec_server.js resets before each
// /exec call and reads afterward, feeding the meter's tool_calls_made.
function makeToolsProxy(baseUrl) {
  const counter = { count: 0 };
  const proxy = new Proxy({}, {
    get(_target, prop) {
      if (typeof prop !== 'string') return undefined;
      return async (args) => {
        counter.count += 1;
        const resp = await fetch(`${baseUrl}/${prop}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(args || {}),
        });
        const result = await resp.json(); // every response is HTTP 200; success/failure is signaled by result.success
        if (!result.success) {
          const err = new Error(`${result.error.code}: ${result.error.technical_message ?? ''}`);
          err.code = result.error.code;
          throw err;
        }
        return result.data;
      };
    },
  });
  return { proxy, counter };
}

module.exports = { makeToolsProxy };
