#!/usr/bin/env node
const fs = require('fs');

const REQUEST_PATH = process.env.MT5_RPC_REQUEST_JSON || 'mt5_rpc_request.json';
const OUTPUT_PATH = process.env.MT5_RPC_OUTPUT_JSON || 'mt5_rpc_output.json';
const RPC_URL = process.env.MT5_RPC_URL || 'http://192.168.8.105:8080/rpc';
const API_KEY = process.env.MT5_RPC_API_KEY || process.env.API_KEY || '';

function fail(msg, extra = {}) {
  const out = { ok: false, error: msg, ...extra };
  fs.writeFileSync(OUTPUT_PATH, JSON.stringify(out, null, 2));
  console.error(msg);
  process.exit(1);
}

function loadRequest() {
  if (!fs.existsSync(REQUEST_PATH)) {
    fail('request_file_not_found', { requestPath: REQUEST_PATH });
  }
  try {
    const raw = fs.readFileSync(REQUEST_PATH, 'utf8');
    const body = JSON.parse(raw);
    if (!body || typeof body !== 'object' || !body.function_name) {
      fail('invalid_request_json', { required: ['function_name'] });
    }
    if (!body.kwargs) body.kwargs = {};
    return body;
  } catch (e) {
    fail('invalid_json_in_request_file', { detail: String(e) });
  }
}

async function run() {
  if (!API_KEY) fail('missing_api_key_env', { requiredEnv: 'MT5_RPC_API_KEY' });

  const payload = loadRequest();

  let res;
  try {
    res = await fetch(RPC_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': API_KEY,
      },
      body: JSON.stringify(payload),
    });
  } catch (e) {
    fail('rpc_request_failed', { detail: String(e), rpcUrl: RPC_URL });
  }

  let data;
  try {
    data = await res.json();
  } catch (e) {
    fail('rpc_non_json_response', { status: res.status, detail: String(e) });
  }

  const out = {
    ok: res.ok && data && data.ok !== false,
    httpStatus: res.status,
    request: payload,
    response: data,
    rpcUrl: RPC_URL,
    timestamp: new Date().toISOString(),
  };

  fs.writeFileSync(OUTPUT_PATH, JSON.stringify(out, null, 2));
  console.log(JSON.stringify(out));

  if (!out.ok) process.exit(2);
}

run();
