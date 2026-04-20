import os
import requests
import json
from dotenv import load_dotenv

load_dotenv(override=True)
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")

def gerar_titulo_misterioso(title):
    """Gera uma frase de mistério/curiosidade curta SEM revelar o desfecho da notícia."""
    if not GEMINI_KEY:
        return "VEJA O QUE ACONTECEU AGORA"
    
    for attempt in range(3):
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GEMINI_KEY}"
            prompt = (
                f"Notícia: \"{title}\"\n"
                f"Crie uma única frase curta de mistério e choque para legenda de Facebook Reels.\n"
                f"REGRAS OBRIGATÓRIAS:\n"
                f"1. NÃO revele o resultado, desfecho ou a notícia em si.\n"
                f"2. Crie CURIOSIDADE EXTREMA para o leitor clicar no link.\n"
                f"3. Use MAIÚSCULAS para dar ênfase.\n"
                f"4. Máximo 10 palavras.\n"
                f"5. Exemplo de tom: 'VEJA O QUE LULA DISSE SOBRE OS INTEGRANTES' ou 'VOCÊ NÃO VAI ACREDITAR NO QUE FOI REVELADO'.\n"
                f"Retorne APENAS a frase, sem explicações, emojis ou aspas."
            )
            payload = {"contents":[{"parts":[{"text":prompt}]}]}
            r = requests.post(url, json=payload, timeout=60)
            r.raise_for_status()
            frase = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            if frase:
                return frase.replace('"', '').upper()
        except Exception as e:
            print(f"Erro ao gerar título misterioso (tentativa {attempt}): {e}")
    
    return "O QUE ACONTECEU VAI TE DEIXAR DE QUEIXO CAÍDO"

def test_format():
    title = "Lula diz que integrantes do Conselho da ONU são senhores da guerra"
    tag = "NA POLÍTICA"
    hashtags = "#lula #onu #politica #guerra #urgente"
    link = "https://topdehoje.com/senhores-da-guerra-diz-lula..."
    
    misterio = gerar_titulo_misterioso(title)
    
    padding_bottom = "\n.\n.\n.\n"
    msg = f"😱 {tag.upper()}: {misterio}... 😱\n.\n{hashtags}{padding_bottom}🔗VEJA MAIS NO LINK: {link}"
    
    print("--- PREVISÃO DA LEGENDA (VER news_debug.txt) ---")
    with open("news_debug_test.txt", "w", encoding="utf-8") as f:
        f.write(msg)
    print("---------------------------")

if __name__ == "__main__":
    test_format()
