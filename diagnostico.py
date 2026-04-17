import os
import requests
from dotenv import load_dotenv

def test_config():
    print("--- DIAGNÓSTICO DE CONFIGURAÇÃO ---")
    load_dotenv(override=True)
    
    page_id = os.environ.get("FB_PAGE_ID")
    token = os.environ.get("FB_TOKEN")
    gemini = os.environ.get("GEMINI_API_KEY")
    
    # 1. Verificar Gemini
    if os.environ.get("GEMINI_API_KEY"):
        print("[OK] Gemini API Key: Presente")
    else:
        print("[ERRO] Gemini API Key: AUSENTE ou inválida no .env")

    # 2. Verificar Facebook
    if not page_id or not token:
        print("[ERRO] Facebook Credentials: ID ou Token ausentes no .env")
        return

    print(f"[INFO] Validando acesso à Página ID: {page_id}")
    url = f"https://graph.facebook.com/v22.0/{page_id}?fields=name&access_token={token}"
    
    try:
        r = requests.get(f"https://graph.facebook.com/v22.0/{page_id}?fields=name&access_token={token}")
        data = r.json()
        
        if "error" in data:
            print(f"[ERRO] Erro na API do Facebook: {data['error'].get('message')}")
            if data['error'].get('code') == 190:
                print("   [AVISO] O Token parece ter EXPIRADO ou é inválido.")
        else:
            nome = data.get("name")
            print(f"[OK] Conexao OK! Nome da Pagina: {nome}")
                
    except Exception as e:
        print(f"[ERRO] Erro de conexão: {e}")

if __name__ == "__main__":
    test_config()
