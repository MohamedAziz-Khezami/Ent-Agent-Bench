// exec_server.js — the /exec endpoint running inside the JS executor
// container. Plain JavaScript only — no TypeScript dependency at all, kept
// fully separate from ts_executor/ so this image's dependency surface stays
// minimal. Uses acorn (a JS-only parser, no type-checker) purely to find the
// trailing bare-expression statement and rewrite it into an explicit
// `return`, since an async function body doesn't auto-return like a raw vm
// script does — this preserves the "trailing expression = the value"
// convention exec_server.py and ts_executor/exec_server.js also implement.
'use strict';
const http = require('http');
const vm = require('vm');
const acorn = require('acorn');
const { makeToolsProxy } = require('./tools_client');

const TOOL_SERVER_URL = process.env.TOOL_SERVER_URL || 'http://localhost:8000';
const { proxy: tools, counter: toolCallCounter } = makeToolsProxy(TOOL_SERVER_URL);
const sandbox = vm.createContext({ tools, console, JSON, Math, Date });

function wrapWithReturn(code) {
  let ast;
  try {
    ast = acorn.parse(code, { ecmaVersion: 2020, sourceType: 'script' });
  } catch {
    return code; // let vm.runInContext surface the real syntax error
  }
  if (ast.body.length === 0) return code;
  const last = ast.body[ast.body.length - 1];
  if (last.type === 'ExpressionStatement') {
    return code.slice(0, last.start) + `return (${code.slice(last.expression.start, last.expression.end)});`;
  }
  return code;
}

async function execBlock(code) {
  let stdout = '', value = null, error = null;
  toolCallCounter.count = 0;
  const origLog = console.log;
  console.log = (...a) => { stdout += a.map(String).join(' ') + '\n'; };
  try {
    const wrapped = `(async () => { ${wrapWithReturn(code)} })()`;
    value = await vm.runInContext(wrapped, sandbox, { timeout: 20000 });
  } catch (e) {
    // "name" is the JS error class (e.g. SyntaxError, TypeError, ReferenceError)
    // so the meter can distinguish a syntax error from a tool error from any
    // other runtime mistake, none of which set a meaningful "code" on their own.
    error = { message: e.message, code: e.code || null, name: e.name || null };
  } finally {
    console.log = origLog;
  }

  let safeValue = null;
  try {
    safeValue = value === undefined ? null : JSON.parse(JSON.stringify(value));
  } catch {
    safeValue = String(value);
  }
  return { ok: !error, stdout, value: safeValue, error, tool_calls: toolCallCounter.count };
}

const server = http.createServer((req, res) => {
  if (req.method === 'GET' && req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ok: true }));
    return;
  }
  if (req.method === 'POST' && req.url === '/exec') {
    let body = '';
    req.on('data', (chunk) => { body += chunk; });
    req.on('end', async () => {
      try {
        const { code } = JSON.parse(body);
        const result = await execBlock(code);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(result));
      } catch (e) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: false, stdout: '', value: null,
                                  error: { message: e.message, code: 'server_error' } }));
      }
    });
    return;
  }
  res.writeHead(404);
  res.end();
});

server.listen(8001, '0.0.0.0', () => {
  console.log('js_executor listening on :8001');
});
