# MT5 RPC Agent

Simple Node agent that talks to your MT5 HTTP RPC gateway.

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

## Run
```bash
cp .env.example .env
# edit .env values
node mt5_rpc_agent.js
```
