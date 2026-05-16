# MT5 RPC Agent

Simple Node agent that talks to your MT5 HTTP RPC gateway.

## Env
- `MT5_RPC_URL` (default: `http://192.168.8.105:8080/rpc`)
- `MT5_RPC_API_KEY` (required)

## Input
- `MT5_RPC_REQUEST_JSON` (default: `mt5_rpc_request.json`)

## Output
- `MT5_RPC_OUTPUT_JSON` (default: `mt5_rpc_output.json`)

## Run
```bash
MT5_RPC_API_KEY='***' node mt5_rpc_agent.js
```
