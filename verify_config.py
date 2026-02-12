"""
Script di verifica rapida della configurazione
"""

import os
from dotenv import load_dotenv

def verify_config():
    """Verifica che tutte le credenziali siano configurate correttamente"""
    load_dotenv()
    
    print("=" * 60)
    print("VERIFICA CONFIGURAZIONE POLYMARKET BOT")
    print("=" * 60)
    
    # Verifica API credentials
    api_key = os.getenv("POLYMARKET_API_KEY")
    api_secret = os.getenv("POLYMARKET_API_SECRET")
    api_passphrase = os.getenv("POLYMARKET_API_PASSPHRASE")
    
    print("\n📋 Credenziali API:")
    print(f"  API Key: {'✅ Configurata' if api_key and api_key != 'your_api_key_here' else '❌ Mancante'}")
    if api_key and api_key != 'your_api_key_here':
        print(f"    Lunghezza: {len(api_key)} caratteri")
    
    print(f"  API Secret: {'✅ Configurata' if api_secret and api_secret != 'your_api_secret_here' else '❌ Mancante'}")
    print(f"  API Passphrase: {'✅ Configurata' if api_passphrase and api_passphrase != 'your_passphrase_here' else '❌ Mancante'}")
    
    # Verifica Private Key
    private_key = os.getenv("PRIVATE_KEY")
    print(f"\n🔑 Chiave Privata:")
    if private_key and private_key != 'your_private_key_here':
        print(f"  ✅ Configurata")
        print(f"  Lunghezza: {len(private_key)} caratteri")
        if len(private_key) < 64:
            print(f"  ⚠️  ATTENZIONE: La chiave privata sembra troppo corta!")
            print(f"     Dovrebbe essere 64 caratteri esadecimali (senza 0x)")
            print(f"     Verifica di aver copiato la chiave completa")
        elif len(private_key) == 64:
            print(f"  ✅ Lunghezza corretta")
        elif len(private_key) == 66 and private_key.startswith('0x'):
            print(f"  ⚠️  La chiave include il prefisso '0x'")
            print(f"     Rimuovi '0x' dal file .env")
    else:
        print(f"  ❌ Mancante")
    
    # Verifica Builder Key
    builder_key = os.getenv("BUILDER_KEY")
    print(f"\n🔧 Builder Key:")
    if builder_key:
        print(f"  ✅ Configurata: {builder_key[:20]}...")
    else:
        print(f"  ❌ Mancante")
    
    # Verifica configurazione
    signature_type = os.getenv("SIGNATURE_TYPE", "0")
    max_position = os.getenv("MAX_POSITION_SIZE", "0.05")
    min_profit = os.getenv("MIN_PROFIT_MARGIN", "0.02")
    
    print(f"\n⚙️  Configurazione:")
    print(f"  Signature Type: {signature_type} ({'EOA' if signature_type == '0' else 'Email/Magic' if signature_type == '1' else 'Safe'})")
    print(f"  Max Position Size: {float(max_position)*100}% del portafoglio")
    print(f"  Min Profit Margin: {float(min_profit)*100}%")
    
    # Verifica completa
    all_configured = all([
        api_key and api_key != 'your_api_key_here',
        api_secret and api_secret != 'your_api_secret_here',
        api_passphrase and api_passphrase != 'your_passphrase_here',
        private_key and private_key != 'your_private_key_here' and len(private_key) >= 64
    ])
    
    print("\n" + "=" * 60)
    if all_configured:
        print("✅ CONFIGURAZIONE COMPLETA!")
        print("=" * 60)
        print("\nProssimi passi:")
        print("1. Testa i componenti: python test_bot.py")
        print("2. Esegui il bot: python bot.py")
    else:
        print("⚠️  CONFIGURAZIONE INCOMPLETA")
        print("=" * 60)
        print("\nVerifica che tutte le credenziali siano configurate correttamente.")
        if private_key and len(private_key) < 64:
            print("\n⚠️  ATTENZIONE: La chiave privata sembra incompleta!")
            print("   Assicurati di aver copiato tutti i 64 caratteri (senza 0x)")

if __name__ == "__main__":
    verify_config()
