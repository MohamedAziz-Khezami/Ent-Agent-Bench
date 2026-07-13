// tools_client.js — lives inside the TS executor container.
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
        const result = await resp.json();
        if (!result.ok) {
          const err = new Error(result.error.message);
          err.code = result.error.code;
          throw err;
        }
        return result.result;
      };
    },
  });
  return { proxy, counter };
}

module.exports = { makeToolsProxy };
