import os
import requests
import json
from dotenv import load_dotenv

load_dotenv(override=True)
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")

titles = [
    "LULA ANUNCIA NOVO PROGRAMA DE MORADIA PARA FAMÍLIAS DE BAIXA RENDA",
    "GABIGOL MARCA NO FIM E FLAMENGO VENCE O VASCO NO MARACANÃ",
    "FAMOSA ATRIZ É FLAGRADA COM NOVO AFFAIR EM RESTAURANTE NO RIO",
    "POLÍCIA CIVIL PRENDE QUADRILHA ESPECIALIZADA EM ROUBO DE CARROS LUXO",
    "BOMBA: NOVO ESCÂNDALO DE CORRUPÇÃO ENVOLVE MINISTRO DO GOVERNO"
]

FB_REACTIONS = {
    "LIKE": "1f44d",
    "LOVE": "2764-fe0f",
    "CARE": "1f917",
    "HAHA": "1f606",
    "WOW": "1f62e",
    "SAD": "1f622",
    "ANGRY": "1f621"
}

def test_caption(title):
    print(f"\n--- Testando: {title} ---")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GEMINI_KEY}"
    prompt = (
        f"Analise a notícia: \"{title}\".\n"
        f"Atue como um editor de notícias sensacionalista de alto impacto.\n"
        f"Retorne APENAS uma linha no formato: HOOK | CATEGORY | EMOJI | HASHTAGS | R1:L1 | R2:L2 | R3:L3\n"
        f"- HOOK: Título EXTREMAMENTE CURTO (MÁXIMO 3 PALAVRAS) em MAIÚSCULAS.\n"
        f"  (Regras de camuflagem omitidas para teste rápido)\n"
        f"- CATEGORY: Escolha exatamente uma: URGENTE, POLITICA, ESPORTE, FOFOCA, CRIME.\n"
        f"- EMOJI: UM único emoji que combine com o tema.\n"
        f"- HASHTAGS: Liste de 3 a 5 hashtags de SEO separadas por espaço, TODAS EM MINÚSCULAS.\n"
        f"- R1, R2, R3: Tipo de reação (LIKE, LOVE, CARE, HAHA, WOW, SAD, ANGRY).\n"
        f"- L1, L2, L3: Opinião curtíssima (máximo 2 palavras). Ex: WOW:Nossa! | SAD:Triste | ANGRY:Absurdo\n"
    )
    payload = {"contents":[{"parts":[{"text":prompt}]}]}
    r = requests.post(url, json=payload, timeout=60)
    if r.status_code == 200:
        raw = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        print(f"Resposta Bruta: {raw}")
        parts = [p.strip() for p in raw.split("|")]
        if len(parts) >= 7:
            print(f"HOOK: {parts[0]}")
            print(f"CAT: {parts[1]}")
            print(f"HASHTAGS: {parts[3]}")
            reactions = []
            for i in range(4, 7):
                if ":" in parts[i]:
                    r_type, r_label = parts[i].split(":", 1)
                    reactions.append((r_type, r_label))
            print(f"REAÇÕES: {reactions}")
        else:
            print("Falha ao parsear resposta (menos de 7 partes)")
    else:
        print(f"Erro Gemini: {r.status_code} - {r.text}")

if __name__ == "__main__":
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    for t in titles:
        test_caption(t)
