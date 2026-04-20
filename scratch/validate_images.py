import os
import requests
import json
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
from dotenv import load_dotenv

load_dotenv(override=True)
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")

# Importar constantes e funções do bot.py (simulado)
FB_REACTIONS = {
    "LIKE": "1f44d",
    "LOVE": "2764-fe0f",
    "CARE": "1f917",
    "HAHA": "1f606",
    "WOW": "1f62e",
    "SAD": "1f622",
    "ANGRY": "1f621"
}

import sys
sys.path.append(os.getcwd())

from bot import baixar_fonte, limpar_emojis, adicionar_texto_premium, gerar_gancho

def validate():
    title = "MORADOR GANHA NA LOTERIA E REVELA O QUE VAI FAZER COM O DINHEIRO EM SÃO PAULO"
    print(f"Testando com título: {title}")
    
    # 1. Gerar Gancho e Reações via IA
    estetica = gerar_gancho(title)
    print(f"Estética gerada: {json.dumps(estetica, indent=2, ensure_ascii=False)}")
    
    # 2. Pegar uma imagem de teste
    img_url = "https://picsum.photos/1080/1080"
    r = requests.get(img_url)
    img_bytes = r.content
    
    # 3. Gerar Imagem Final
    img_final_bytes = adicionar_texto_premium(img_bytes, estetica)
    
    # 4. Salvar
    output_path = "preview_dynamic_reactions.jpg"
    with open(output_path, "wb") as f:
        f.write(img_final_bytes)
    
    print(f"✅ Imagem de validação salva em: {output_path}")

if __name__ == "__main__":
    validate()
