import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict
import os
import signal
import subprocess
import atexit
import MetaTrader5 as mt5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger("mt5-gateway")

API_KEY = "***"
ACCOUNT = ****
PASSWORD = "***"
SERVER = "***"

ALLOWED_FUNCTIONS = {
    "account_info",
    "copy_rates_from",
    "copy_rates_from_pos",
    "copy_ticks_from",
    "history_deals_get",
    "history_orders_get",
    "order_check",
    "order_send",
    "orders_get",
    "positions_get",
    "symbol_info",
    "symbol_info_tick",
    "symbols_get",
    "symbols_total",
    "terminal_info",
    "version",
}

_CLOSED = False

class RpcBody(BaseModel):
    function_name: str
    kwargs: Dict[str, Any] = Field(default_factory=dict)


def to_jsonable(obj: Any):
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, list):
        return [to_jsonable(x) for x in obj]
    if isinstance(obj, tuple):
        return [to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if hasattr(obj, "_asdict"):
        return {k: to_jsonable(v) for k, v in obj._asdict().items()}
    return str(obj)

def kill_mt5_terminal():
    # Works on Windows host only
    if os.name != "nt":
        return

    mt5_path = os.getenv("MT5_PATH", "").strip()
    image = os.path.basename(mt5_path) if mt5_path else "terminal64.exe"
    if not image.lower().endswith(".exe"):
        image = "terminal64.exe"

    for name in [image, "terminal64.exe"]:
        subprocess.run(
            ["taskkill", "/F", "/IM", name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def shutdown_cleanup():
    global _CLOSED
    if _CLOSED:
        return
    _CLOSED = True

    try:
        mt5.shutdown()
    except Exception:
        pass

    # Your requirement: kill MT5 terminal before app fully stops
    kill_mt5_terminal()


def _handle_stop(signum, frame):
    shutdown_cleanup()
    raise SystemExit(0)



def call_mt5(fn, fn_name: str, kwargs: Dict[str, Any]):
    # 1) Try native kwargs first
    try:
        return fn(**kwargs) if kwargs else fn()
    except TypeError as e:
        msg = str(e).lower()
        if "keyword" not in msg:
            raise

    # 2) Fallback mapping for MT5 funcs that require positional args
    pos_order = {
        "symbol_info": ["symbol"],
        "symbol_info_tick": ["symbol"],
        "copy_rates_from": ["symbol", "timeframe", "date_from", "count"],
        "copy_rates_from_pos": ["symbol", "timeframe", "start_pos", "count"],
        "copy_ticks_from": ["symbol", "date_from", "count", "flags"],
    }

    keys = pos_order.get(fn_name)
    if keys and all(k in kwargs for k in keys):
        return fn(*[kwargs[k] for k in keys])

    # 3) Generic single-arg fallback (e.g., any symbol)
    if len(kwargs) == 1:
        return fn(next(iter(kwargs.values())))

    raise TypeError(f"{fn_name}: cannot map kwargs to positional args: {kwargs}")

def mt5_connect(max_retries: int = 5, delay_sec: float = 2.0) -> None:
    for attempt in range(1, max_retries + 1):
        if mt5.initialize(login=ACCOUNT, password=PASSWORD, server=SERVER):
            log.info("MT5 connected on attempt %s", attempt)
            return
        err = mt5.last_error()
        log.warning("MT5 connect attempt %s failed: %s", attempt, err)
        mt5.shutdown()
        time.sleep(delay_sec)
    raise RuntimeError(f"MT5 connection failed after retries: {mt5.last_error()}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    mt5_connect()
    try:
        yield
    finally:
        shutdown_cleanup()
app = FastAPI(title="MT5 RPC Gateway", version="1.2.0", lifespan=lifespan)

@app.get("/health")
def health():
    return {"ok": True}


@app.get("/allowed_functions")
def allowed_functions():
    return {"functions": sorted(ALLOWED_FUNCTIONS)}


@app.post("/rpc")
def rpc(body: RpcBody, x_api_key: str = Header(default="")):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid api key")

    fn_name = body.function_name
    if fn_name not in ALLOWED_FUNCTIONS:
        raise HTTPException(status_code=400, detail=f"function not allowed: {fn_name}")

    fn = getattr(mt5, fn_name, None)
    if fn is None:
        raise HTTPException(status_code=400, detail=f"function not found: {fn_name}")

    kwargs = dict(body.kwargs or {})

    try:
        result = call_mt5(fn, fn_name, kwargs)
        return {"ok": True, "result": to_jsonable(result)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# Ensure Ctrl+C / SIGTERM also runs cleanup
atexit.register(shutdown_cleanup)
signal.signal(signal.SIGINT, _handle_stop)
signal.signal(signal.SIGTERM, _handle_stop)
