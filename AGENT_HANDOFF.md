# AGENT_HANDOFF.md

## Purpose
This repo runs an MT5 RPC gateway and helper agent for querying/trading via HTTP.

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

## Common calls
- account info: `{"function_name":"account_info"}`
- terminal info: `{"function_name":"terminal_info"}`
- open positions: `{"function_name":"positions_get"}`
- pending orders: `{"function_name":"orders_get"}`
- tick: `{"function_name":"symbol_info_tick","kwargs":{"symbol":"BTCUSD"}}`

## Known behavior notes
- MT5 Python functions may reject keyword args for some methods; gateway maps selected kwargs to positional args.
- If RPC returns `ok:true` with `result:null`, MT5 session/terminal may be inactive; restart via scripts.
- Task Scheduler “End task” can be hard-kill; prefer controlled stop via `stop_gateway.ps1`.

## Security
- Keep real credentials only in `.env` on host.
- Do not commit secrets.
- Rotate API key if exposed.
