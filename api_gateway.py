import time
import logging
from pathlib import Path
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


def load_local_env():
    candidates = [
        Path(__file__).resolve().parent / ".env",
        Path.cwd() / ".env",
    ]
    for p in candidates:
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            k = k.strip()
            v = v.strip()
            if k and k not in os.environ:
                os.environ[k] = v
        return str(p)
    return None


_env_loaded_from = load_local_env()
if _env_loaded_from:
    log.info("Loaded .env from %s", _env_loaded_from)

API_KEY = os.getenv("API_KEY", "").strip()
ACCOUNT = int(os.getenv("MT5_ACCOUNT", os.getenv("MT5_LOGIN", "0")) or 0)
PASSWORD = os.getenv("MT5_PASSWORD", "")
SERVER = os.getenv("MT5_SERVER", "")
MT5_PATH = os.getenv("MT5_PATH", "").strip()

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


ACTION_MAP = {
    "deal": mt5.TRADE_ACTION_DEAL,
    "pending": mt5.TRADE_ACTION_PENDING,
    "sltp": mt5.TRADE_ACTION_SLTP,
    "modify": mt5.TRADE_ACTION_MODIFY,
    "remove": mt5.TRADE_ACTION_REMOVE,
}

ORDER_TYPE_MAP = {
    "buy": mt5.ORDER_TYPE_BUY,
    "sell": mt5.ORDER_TYPE_SELL,
    "buy_limit": mt5.ORDER_TYPE_BUY_LIMIT,
    "sell_limit": mt5.ORDER_TYPE_SELL_LIMIT,
    "buy_stop": mt5.ORDER_TYPE_BUY_STOP,
    "sell_stop": mt5.ORDER_TYPE_SELL_STOP,
}

TYPE_TIME_MAP = {
    "gtc": mt5.ORDER_TIME_GTC,
    "day": mt5.ORDER_TIME_DAY,
    "specified": mt5.ORDER_TIME_SPECIFIED,
    "specified_day": mt5.ORDER_TIME_SPECIFIED_DAY,
}

TYPE_FILLING_MAP = {
    "fok": mt5.ORDER_FILLING_FOK,
    "ioc": mt5.ORDER_FILLING_IOC,
    "return": mt5.ORDER_FILLING_RETURN,
}


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
    if os.name != "nt":
        return

    image = os.path.basename(MT5_PATH) if MT5_PATH else "terminal64.exe"
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

    kill_mt5_terminal()


def _handle_stop(signum, frame):
    shutdown_cleanup()
    raise SystemExit(0)


def call_mt5(fn, fn_name: str, kwargs: Dict[str, Any]):
    try:
        return fn(**kwargs) if kwargs else fn()
    except TypeError as e:
        msg = str(e).lower()
        if "keyword" not in msg:
            raise

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

    if len(kwargs) == 1:
        return fn(next(iter(kwargs.values())))

    raise TypeError(f"{fn_name}: cannot map kwargs to positional args: {kwargs}")


def _as_int(v):
    try:
        return int(v)
    except Exception:
        return None


def _as_float(v):
    try:
        return float(v)
    except Exception:
        return None


def _map_enum(value, mapper):
    if isinstance(value, str):
        return mapper.get(value.strip().lower(), value)
    return value


def normalize_trade_request(request: Dict[str, Any]) -> Dict[str, Any]:
    req = dict(request or {})

    req["action"] = _map_enum(req.get("action"), ACTION_MAP)
    req["type"] = _map_enum(req.get("type"), ORDER_TYPE_MAP)
    req["type_time"] = _map_enum(req.get("type_time", mt5.ORDER_TIME_GTC), TYPE_TIME_MAP)
    req["type_filling"] = _map_enum(req.get("type_filling", mt5.ORDER_FILLING_RETURN), TYPE_FILLING_MAP)

    for k in ("volume", "price", "sl", "tp", "stoplimit"):
        if k in req and req[k] is not None:
            fv = _as_float(req[k])
            if fv is not None:
                req[k] = fv

    for k in ("deviation", "magic", "position", "order", "expiration"):
        if k in req and req[k] is not None:
            iv = _as_int(req[k])
            if iv is not None:
                req[k] = iv

    symbol = str(req.get("symbol", "") or "").upper()
    if symbol:
        req["symbol"] = symbol
        try:
            info = mt5.symbol_info(symbol)
            if info is not None and not info.visible:
                mt5.symbol_select(symbol, True)
            if info is not None:
                digits = int(getattr(info, "digits", 2) or 2)
                for k in ("price", "sl", "tp", "stoplimit"):
                    if k in req and isinstance(req[k], (int, float)):
                        req[k] = round(float(req[k]), digits)
        except Exception:
            pass

    return req


def call_trade_function(fn_name: str, kwargs: Dict[str, Any]):
    request = kwargs.get("request") if isinstance(kwargs, dict) else None
    if not isinstance(request, dict):
        raise ValueError(f"{fn_name} requires kwargs.request object")

    req = normalize_trade_request(request)

    if fn_name == "order_check":
        return mt5.order_check(req)
    return mt5.order_send(req)


def mt5_connect(max_retries: int = 5, delay_sec: float = 2.0) -> None:
    for attempt in range(1, max_retries + 1):
        init_kwargs = {}
        if MT5_PATH:
            init_kwargs["path"] = MT5_PATH

        if ACCOUNT and PASSWORD and SERVER:
            ok = mt5.initialize(login=ACCOUNT, password=PASSWORD, server=SERVER, **init_kwargs)
        else:
            ok = mt5.initialize(**init_kwargs)

        if ok:
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


app = FastAPI(title="MT5 RPC Gateway", version="1.2.1", lifespan=lifespan)


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
        if fn_name in ("order_send", "order_check"):
            result = call_trade_function(fn_name, kwargs)
            return {
                "ok": True,
                "result": to_jsonable(result),
                "normalized_request": to_jsonable(normalize_trade_request(kwargs.get("request") or {})),
            }

        result = call_mt5(fn, fn_name, kwargs)
        return {"ok": True, "result": to_jsonable(result)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


atexit.register(shutdown_cleanup)
signal.signal(signal.SIGINT, _handle_stop)
signal.signal(signal.SIGTERM, _handle_stop)
