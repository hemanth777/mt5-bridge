# MT5 RPC Agent

Simple Node agent that talks to your MT5 HTTP RPC gateway.

This package is bridge-local. It should only know the gateway request/response contract and connection config, not higher-level Telegram or orchestration logic from the main MT5 workspace.

## Env
The agent auto-loads `.env` from this folder.

- `MT5_RPC_API_KEY` (required)
- `MT5_RPC_HOST` (default: `192.168.8.105`)
- `MT5_RPC_PORT` (default: `8080`)
- `MT5_RPC_SCHEME` (default: `http`)
- `MT5_RPC_URL` (optional full override; takes priority)

## Input
- `MT5_RPC_REQUEST_JSON` (default: `mt5_rpc_request.json`)

## Output
- `MT5_RPC_OUTPUT_JSON` (default: `mt5_rpc_output.json`)

## Notes
- HTTP `200` does not guarantee a trade was accepted; inspect the returned MT5 result payload.
- Prefer `MT5_RPC_URL` when the gateway address is managed externally.

## Run
```bash
cp .env.example .env
# edit .env values
node mt5_rpc_agent.js
```
