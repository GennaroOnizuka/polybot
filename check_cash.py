#!/usr/bin/env python3
"""
Script secondario: controlla solo il cash (USDC) sul conto Polymarket.
Usa stesso .env, proxy e CLOB del bot. Nessun ordine, nessun trading.
Uso: python3 check_cash.py
"""

import os
import sys
from urllib.parse import urlparse, quote_plus

from dotenv import load_dotenv
load_dotenv()


def _get_proxy_url() -> str:
    """URL proxy da .env (come bot e test_connection)."""
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


def _setup_proxy() -> None:
    """Attiva proxy per il client CLOB."""
    proxy_url = _get_proxy_url()
    if not proxy_url:
        return
    os.environ["HTTP_PROXY"] = proxy_url
    os.environ["HTTPS_PROXY"] = proxy_url
    os.environ["ALL_PROXY"] = proxy_url
    import httpx
    import py_clob_client.http_helpers.helpers as _h
    _h._http_client = httpx.Client(http2=True, proxy=proxy_url, timeout=30.0)


def main():
    if not os.getenv("PRIVATE_KEY"):
        print("ERRORE: PRIVATE_KEY mancante in .env", file=sys.stderr)
        sys.exit(1)

    _setup_proxy()

    api_key = os.getenv("POLYMARKET_API_KEY", "").strip()
    api_secret = os.getenv("POLYMARKET_API_SECRET", "").strip()
    api_passphrase = os.getenv("POLYMARKET_API_PASSPHRASE", "").strip()
    private_key = (os.getenv("PRIVATE_KEY") or "").strip()
    if private_key and not private_key.startswith("0x"):
        private_key = "0x" + private_key
    if private_key.startswith("0x"):
        private_key = private_key[2:]
    signature_type = int(os.getenv("SIGNATURE_TYPE", "0"))

    try:
        from executor import OrderExecutor
        ex = OrderExecutor(
            api_key=api_key or "",
            api_secret=api_secret or "",
            api_passphrase=api_passphrase or "",
            private_key=private_key,
            signature_type=signature_type,
        )
        balance = ex.get_balance()
        print(f"Cash: {balance:.2f} USDC")
    except Exception as e:
        print(f"Errore: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
