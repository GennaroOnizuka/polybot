#!/usr/bin/env python3
"""
Test stabilità IP proxy (sticky session).
Esegue 5 richieste consecutive e verifica se l'IP resta lo stesso.
Se vedi 5 IP diversi → sticky session non funziona.
Se vedi 1 solo IP → sticky session funziona.
"""
import os
import json
import time
from urllib.parse import urlparse

from dotenv import load_dotenv
load_dotenv()

# Usa lo stesso proxy del bot (PROXY_URL)
proxy_url = os.getenv("PROXY_URL", "").strip()
if not proxy_url:
    print("PROXY_URL non impostato in .env")
    exit(1)

print("Testing proxy (sticky session)...")
print(f"  URL: {urlparse(proxy_url).hostname}:{urlparse(proxy_url).port}")
print()

# Configura proxy per urllib
proxy_handler = __import__("urllib.request").ProxyHandler({
    "http": proxy_url,
    "https": proxy_url,
})
opener = __import__("urllib.request").build_opener(proxy_handler)
__import__("urllib.request").install_opener(opener)

urllib_request = __import__("urllib.request")
ips = []

for i in range(5):
    try:
        req = urllib_request.Request(
            "http://ip-api.com/json/?fields=query,country,countryCode",
            headers={"User-Agent": "Polybot"},
        )
        with urllib_request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        ip = data.get("query", "?")
        country = data.get("countryCode", "?")
        ips.append(ip)
        print(f"  Richiesta {i+1}: IP={ip}  Paese={country}")
        time.sleep(1)
    except Exception as e:
        print(f"  Richiesta {i+1}: Errore — {e}")

unique_ips = set(ips)
print()
print("Risultato:")
print(f"  IP unici: {len(unique_ips)}")
print(f"  IPs: {unique_ips}")

if len(unique_ips) == 1:
    print("  Sticky session attiva: stesso IP per tutte le richieste.")
else:
    print("  L’IP ruota: sticky session non attiva o formato errato.")
    print("  Verifica in .env: username-session-XXXX:password@host:port")
