#!/usr/bin/env python3
"""
Script SOLO CONNESSIONE: verifica proxy + CLOB + chiavi API (L1/L2).
Nessun ordine, nessun trading. Se OK, le stesse chiavi vanno bene per bot_async.py.
Uso: python3 test_connection.py
"""

import os
import sys
from urllib.parse import urlparse, quote_plus

from dotenv import load_dotenv
load_dotenv()


def _get_proxy_url() -> str:
    """URL proxy da .env (come bot_async)."""
    proxy_url = os.getenv("PROXY_URL", "").strip()
    if not proxy_url:
        host = os.getenv("PROXY_HOST", "").strip()
        port = os.getenv("PROXY_PORT", "").strip()
        if host and port:
            user = os.getenv("PROXY_USER", "").strip()
            password = os.getenv("PROXY_PASSWORD", "").strip() or os.getenv("PROXY_PASS", "").strip()
            if user and password:
                proxy_url = f"http://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}"
            else:
                proxy_url = f"http://{host}:{port}"
    return proxy_url


def _setup_proxy() -> bool:
    """Attiva proxy per tutto il traffico (incluso CLOB). Ritorna True se proxy configurato."""
    proxy_url = _get_proxy_url()
    if not proxy_url:
        print("Proxy: non configurato (PROXY_URL vuoto)")
        return False
    os.environ["HTTP_PROXY"] = proxy_url
    os.environ["HTTPS_PROXY"] = proxy_url
    os.environ["ALL_PROXY"] = proxy_url
    import httpx
    import py_clob_client.http_helpers.helpers as _h
    _h._http_client = httpx.Client(http2=True, proxy=proxy_url, timeout=30.0)
    p = urlparse(proxy_url)
    print(f"Proxy: attivo → {p.hostname}:{p.port or 823}")
    # Quick exit-IP check
    try:
        import requests
        r = requests.get(
            "https://api.ipify.org?format=json",
            proxies={"http": proxy_url, "https": proxy_url},
            timeout=10,
        )
        r.raise_for_status()
        print(f"  Exit IP: {r.text.strip()}")
    except Exception as e:
        print(f"  Exit IP check: {e}")
    return True


def main():
    print("=" * 50)
    print("POLYBOT — Test solo connessione (proxy + CLOB + chiavi)")
    print("=" * 50)

    if not os.getenv("PRIVATE_KEY"):
        print("ERRORE: PRIVATE_KEY mancante in .env")
        sys.exit(1)

    # 1) Proxy (stesso setup del bot)
    _setup_proxy()

    # 2) CLOB client + L2 (stesso init di bot_async → OrderExecutor)
    from executor import OrderExecutor

    api_key = os.getenv("POLYMARKET_API_KEY")
    api_secret = os.getenv("POLYMARKET_API_SECRET")
    api_passphrase = os.getenv("POLYMARKET_API_PASSPHRASE")
    private_key = (os.getenv("PRIVATE_KEY") or "").strip()
    if private_key and not private_key.startswith("0x"):
        private_key = "0x" + private_key
    if private_key.startswith("0x"):
        private_key = private_key[2:]
    signature_type = int(os.getenv("SIGNATURE_TYPE", "0"))

    try:
        ex = OrderExecutor(
            api_key=api_key or "",
            api_secret=api_secret or "",
            api_passphrase=api_passphrase or "",
            private_key=private_key,
            signature_type=signature_type,
        )
    except Exception as e:
        print(f"ERRORE init CLOB: {e}")
        sys.exit(1)

    # 3) Saldo reale (L2 auth) — risposta raw + valore letto
    print("\n--- Saldo (CLOB L2) ---")
    from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
    from py_clob_client.exceptions import PolyApiException
    try:
        params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=-1)
        balance_info = ex.client.get_balance_allowance(params)
        print(f"  Risposta API (raw): {balance_info}")
        if isinstance(balance_info, dict):
            bal = balance_info.get("available") or balance_info.get("balance") or balance_info.get("usdc") or balance_info.get("size") or 0
        elif isinstance(balance_info, (int, float)):
            bal = float(balance_info)
        elif isinstance(balance_info, list):
            bal = 0.0
            for item in balance_info:
                if isinstance(item, dict) and (item.get("currency") == "USDC" or "available" in item or "balance" in item):
                    bal = float(item.get("available", item.get("balance", 0)))
                    break
        else:
            bal = 0.0
        # API restituisce micro-USDC (6 decimali)
        print(f"\n  >>> SALDO USDC: {float(bal) / 1e6:.2f} <<<")
        print("  L2 auth OK.")
    except PolyApiException as e:
        code = getattr(e, "status_code", None)
        msg = getattr(e, "error_msg", str(e))
        print(f"  Errore CLOB: {code} — {msg}")
        if code == 401:
            print("\n  PERCHÉ NON SI CONNETTE:")
            print("  La chiave che hai (019c5384-...) è quasi certamente una BUILDER KEY (Settings → Builder Codes).")
            print("  Il CLOB per trading usa credenziali DIVERSE, create solo via API (derive).")
            print("\n  Provo a DERIVARE le credenziali giuste ora (L1 = tua PRIVATE_KEY)...")
            try:
                ex.client.set_api_creds(ex.client.create_or_derive_api_creds())
                params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=-1)
                balance_info = ex.client.get_balance_allowance(params)
                print(f"  Risposta API (raw): {balance_info}")
                if isinstance(balance_info, dict):
                    bal = balance_info.get("available") or balance_info.get("balance") or balance_info.get("usdc") or balance_info.get("size") or 0
                else:
                    bal = float(balance_info) if isinstance(balance_info, (int, float)) else 0.0
                print(f"\n  >>> SALDO USDC: {float(bal) / 1e6:.2f} <<<")
                creds = ex.client.creds
                print("\n  Aggiungi queste righe al .env (sostituisci le vecchie):")
                print(f"  POLYMARKET_API_KEY={creds.api_key}")
                print(f"  POLYMARKET_API_SECRET={creds.api_secret}")
                print(f"  POLYMARKET_API_PASSPHRASE={creds.api_passphrase}")
                print("\n  Poi riesegui test_connection.py — vedrai il saldo senza 401.")
            except Exception as e2:
                print(f"  Derive fallito: {e2}")
                print("  Nel .env lascia VUOTE POLYMARKET_API_KEY, SECRET, PASSPHRASE e riesegui.")
            sys.exit(1)
        raise
    except Exception as e:
        print(f"  get_balance fallito: {e}")
        sys.exit(1)

    # 4) Test lettura orderbook (proxy verso CLOB)
    print("\nTest orderbook (proxy CLOB)...")
    try:
        test_token = "114824063543946450418324122202886293655209258039133501121134745662852474986880"
        ob = ex.get_orderbook(test_token)
        if ob:
            print("  Orderbook ricevuto OK.")
        else:
            print("  Orderbook vuoto.")
    except Exception as e:
        print(f"  Orderbook: {e} (404 = token non più attivo, normale)")

    print("\n" + "=" * 50)
    print("Connessione OK. Saldo letto sopra. Stesse chiavi per bot_async.py")
    print("=" * 50)


if __name__ == "__main__":
    main()
