# AGENT_HANDOFF.md

## Purpose
This repo runs an MT5 RPC gateway and helper agent for querying/trading via HTTP.

## Scope boundary
This repo is only for the MT5 bridge layer:
- the FastAPI RPC gateway
- the Windows start/stop lifecycle scripts
- the local `mt5-rpc-agent` client and call catalog

It is not the home for higher-level trading pipeline behavior from the main workspace.
Keep Telegram listener, signal-conversion, risk-routing, backfill, watchdog, and notification logic documented outside this repo unless the bridge contract itself changes.

## What matters most
- `api_gateway.py`: FastAPI app exposing `/health`, `/allowed_functions`, `/rpc`
- `start_gateway.ps1`: starts dedicated MT5 terminal + gateway, stores PID files
- `stop_gateway.ps1`: stops only tracked PIDs (gateway first, then MT5)
- `mt5-rpc-agent/`: simple Node client + call catalog

## Runtime assumptions
- Windows MT5 host
- MT5 terminal available (`terminal64.exe`)
- Python env has `MetaTrader5`, `fastapi`, `uvicorn`

## Required env vars
- `API_KEY`
- `MT5_ACCOUNT` (or `MT5_LOGIN`)
- `MT5_PASSWORD`
- `MT5_SERVER`
- Optional: `MT5_PATH`

## Start/stop behavior
- Start script checks if existing `gateway.pid` is alive; if yes, runs stop first.
- Starts dedicated MT5 terminal with `/portable` and then gateway.
- Writes `mt5.pid` and `gateway.pid`.
- Stop script kills only those tracked PIDs to avoid touching unrelated MT5 terminals.

### Script configuration source (.env)
- `start_gateway.ps1` and `stop_gateway.ps1` load `.env` from the same folder as the script (`$PSScriptRoot\.env`).
- Task Scheduler does not load `.env` itself; it only runs the script.
- Required placement on host: `C:\mt5-bridge\.env` (if scripts are in `C:\mt5-bridge`).
- Script-level config keys:
  - `BRIDGE_ROOT` (optional; defaults to script folder)
  - `MT5_DIR`
  - `MT5_EXE`

## RPC contract
POST `/rpc` body:
```json
{
  "function_name": "symbol_info_tick",
  "kwargs": { "symbol": "BTCUSD" }
}
```
Auth header:
- `x-api-key: <API_KEY>`

Response shape:
- success wrapper: `{ "ok": true, "result": ... }`
- failure wrapper: `{ "ok": false, "error": "..." }`
- some MT5 failures can still arrive as HTTP 200 with a rejected trade result inside `result`

## Common calls
- account info: `{"function_name":"account_info"}`
- terminal info: `{"function_name":"terminal_info"}`
- open positions: `{"function_name":"positions_get"}`
- pending orders: `{"function_name":"orders_get"}`
- tick: `{"function_name":"symbol_info_tick","kwargs":{"symbol":"BTCUSD"}}`
- order history: `{"function_name":"history_orders_get","kwargs":{"date_from":"<ISO>","date_to":"<ISO>"}}`
- deal history: `{"function_name":"history_deals_get","kwargs":{"date_from":"<ISO>","date_to":"<ISO>"}}`

## Known behavior notes
- MT5 Python functions may reject keyword args for some methods; gateway maps selected kwargs to positional args.
- If RPC returns `ok:true` with `result:null`, MT5 session/terminal may be inactive; restart via scripts.
- Trade requests must still inspect the MT5 trade result/retcode, not just the HTTP status.
- Task Scheduler “End task” can be hard-kill; prefer controlled stop via `stop_gateway.ps1`.

## Out of scope
Do not treat this file as the handoff doc for:
- Telegram feed listener watchdog behavior
- restart-safe Telegram backfill or channel state files
- signal conversion and validation model policy
- risk guard or route-selection policy
- Telegram execution notifications

Those belong to the main workspace MT5 orchestration docs, not the standalone bridge repo.

## Security
- Keep real credentials only in `.env` on host.
- Do not commit secrets.
- Rotate API key if exposed.
