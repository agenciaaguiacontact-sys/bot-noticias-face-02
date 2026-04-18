#!/usr/bin/env python3
"""
SharesForYou → Facebook Auto-Poster Bot
Versão FINAL ABSOLUTA - Noticiário Profissional
"""

import os
import json
import time
import logging
import hashlib
import textwrap
import requests
import random
import re
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
from requests.adapters import HTTPAdapter
import traceback
import subprocess
import glob
from dotenv import load_dotenv

load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# Configurações
SFY_EMAIL    = os.environ.get("SFY_EMAIL", "")
SFY_PASSWORD = os.environ.get("SFY_PASSWORD", "")
FB_PAGE_ID   = os.environ.get("FB_PAGE_ID", "122181202022766925")
FB_TOKEN     = os.environ.get("FB_TOKEN", "")
GEMINI_KEY   = os.environ.get("GEMINI_API_KEY", "")

POSTED_FILE  = "posted_ids.json"
SFY_SHARE    = "https://www.sharesforyou.com/dashboard/share"
SFY_LOGIN    = "https://www.sharesforyou.com/login"
FB_GRAPH     = "https://graph.facebook.com/v22.0"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}



def make_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    r = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=r))
    return s

def load_posted():
    if os.path.exists(POSTED_FILE):
        try: return set(json.load(open(POSTED_FILE)))
        except: return set()
    return set()

def save_posted(ids):
    json.dump(sorted(list(ids))[-500:], open(POSTED_FILE, "w"), indent=2)

def make_article_id(url):
    # Remove query strings para evitar duplicatas por parâmetros de rastreio
    clean_url = url.split("?")[0].split("#")[0]
    return hashlib.sha256(clean_url.encode()).hexdigest()[:16]

def load_last_title():
    if os.path.exists("last_title.txt"):
        try: return open("last_title.txt", "r", encoding="utf-8").read().strip()
        except: return ""
    return ""

def save_last_title(title):
    try: open("last_title.txt", "w", encoding="utf-8").write(title)
    except: pass

def baixar_fonte(emoji=False):
    # Priorizar fonte local para compatibilidade com Nuvem (Linux)
    local_impact = os.path.join("fonts", "impact.ttf")
    if os.path.exists(local_impact): return local_impact

    if emoji:
        for f in ["C:\\Windows\\Fonts\\seguiemj.ttf"]:
            if os.path.exists(f): return f
            
    # Fallbacks de sistema
    for f in ["C:\\Windows\\Fonts\\impact.ttf", "fonts/NotoSans-Bold.ttf", "C:\\Windows\\Fonts\\arialbd.ttf"]:
        if os.path.exists(f): return f
    return None

def limpar_emojis(texto):
    # Preserva caracteres acentuados e pontuação, removendo apenas o que não é texto 'humano'
    return re.sub(r'[^\w\s.,!?;:\"\'\(\)\-\u00C0-\u00FF]+', '', texto).strip()

# Mapeamento de emojis de reação do Facebook por categoria
# Cada lista contém tuplas (emoji_hex, label) — máximo 3 por categoria
# CRIME não tem reações
REACTION_EMOJIS_BY_CATEGORY = {
    "URGENTE":  [("1f44d", "Absurdo!"),   ("1f622", "Que triste"),  ("1f621", "Indignado")],
    "POLITICA": [("1f44d", "Concordo"),   ("2764",  "Apoio"),       ("1f62e", "Chocante")],
    "ESPORTE":  [("1f44d", "Top demais!"), ("1f606", "Haha"),        ("1f62e", "Incrível")],
    "FOFOCA":   [("1f606", "Inacreditável"),("2764", "Amei"),        ("1f62e", "Nossa!")],
    "CRIME":    [],  # Sem emojis de engajamento para notícias de crime
}

def gerar_gancho(title):
    default_res = {
        "hook": "REVELAÇÃO CHOCANTE!", "tag": "NOTÍCIA URGENTE",
        "color": (255, 0, 0, 200), "emoji": "1f6a8",
        "hashtags": "#noticias #urgente",
        "category": "URGENTE",
        "reactions": REACTION_EMOJIS_BY_CATEGORY["URGENTE"]
    }
    if not GEMINI_KEY: return default_res
    
    last_t = load_last_title()
    
    # Mapeamento de Categorias, Cores e Tags
    CATEGORIES = {
        "URGENTE": {"tag": "NOTÍCIA URGENTE", "color": (255, 0, 0, 200)},
        "POLITICA": {"tag": "NA POLÍTICA", "color": (0, 102, 255, 200)},
        "ESPORTE": {"tag": "NO ESPORTE", "color": (50, 205, 50, 200)},
        "FOFOCA": {"tag": "VOCÊ NÃO VAI ACREDITAR", "color": (255, 215, 0, 200)},
        "CRIME": {"tag": "CRIME AGORA", "color": (0, 0, 0, 200)},
    }
    
    EMOJI_HEX = {
        "🚨": "1f6a8", "💀": "1f480", "🔥": "1f525", "💣": "1f4a3", "⚠️": "26a0", 
        "😱": "1f631", "👀": "1f440", "📢": "1f4e2", "💰": "1f4b0", "🚔": "1f694",
        "⚽": "26bd", "🎭": "1f3ad", "🤐": "1f910"
    }

    for attempt in range(3):
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GEMINI_KEY}"
            prompt = (
                f"Analise a notícia: \"{title}\".\n"
                f"Atue como um editor de notícias sensacionalista de alto impacto.\n"
                f"Retorne APENAS uma linha no formato: HOOK | CATEGORY | EMOJI | HASHTAGS\n"
                f"- HOOK: Título EXTREMAMENTE CURTO (MÁXIMO 3 PALAVRAS) em MAIÚSCULAS.\n"
                f"  REGRA DE CAMUFLAGEM: substitua letras por numeros/simbolos SOMENTE se o HOOK\n"

                f"  contiver EXATAMENTE uma destas palavras proibidas:\n"

                f"  MORTE, MORTO, MORREU, MATAR, MATOU, MATARAM, ASSASSINOU, ASSASSINATO,\n"

                f"  ESPANCOU, SANGUE, TIRO, TIROS, BALEADO, ESTUPRO, ESTUPROU, ABUSO,\n"

                f"  TRAFICO, DROGA, DROGAS, COCAINA, CRACK.\n"

                f"  Exemplos CORRETOS: MORTE->M0RT3, MATOU->M@T0U, TIRO->T1R0, SANGUE->S@NGU3, ESTUPRO->3STUPR0.\n"

                f"  PROIBIDO substituir letras em qualquer outra palavra. Exemplos INTACTOS:\n"

                f"  BALE, INSANO, INVASAO, COPA, TREINO, BRASIL, POLICIA, ACIDENTE, ESPORTE,\n"

                f"  VENCE, GANHA, REVELA, FLAGRA, CHOCA, SURPREENDE, BRIGA, CRISE, e qualquer outra.\n"

                f"- CATEGORY: Escolha exatamente uma: URGENTE, POLITICA, ESPORTE, FOFOCA, CRIME.\n"
                f"- EMOJI: UM único emoji que combine com o tema.\n"
                f"- HASHTAGS: Liste de 3 a 5 hashtags de SEO separadas por espaço, TODAS EM MINÚSCULAS (ex: #noticias #brasil #urgente).\n"
                f"Não repita o último título: \"{last_t}\"."
            )
            payload = {"contents":[{"parts":[{"text":prompt}]}]}
            r = requests.post(url, json=payload, timeout=60)
            r.raise_for_status()
            raw = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            
            if "|" in raw:
                parts = [p.strip() for p in raw.split("|")]
                if len(parts) >= 3:
                    hook = parts[0].replace('"', '').upper()
                    cat_key = parts[1].upper()
                    emoji_char = parts[2]
                    # Etapa 2: garantir hashtags todas em minúsculas
                    hashtags_raw = parts[3] if len(parts) >= 4 else "#noticias #brasil #urgente"
                    hashtags = hashtags_raw.lower()
                    
                    if hook != last_t:
                        save_last_title(hook)
                        config = CATEGORIES.get(cat_key, CATEGORIES["URGENTE"])
                        emoji_hex = EMOJI_HEX.get(emoji_char, "1f525")
                        reactions = REACTION_EMOJIS_BY_CATEGORY.get(cat_key, REACTION_EMOJIS_BY_CATEGORY["URGENTE"])
                        return {
                            "hook": hook, 
                            "tag": config["tag"],
                            "color": config["color"], 
                            "emoji": emoji_hex,
                            "hashtags": hashtags,
                            "category": cat_key,
                            "reactions": reactions,
                        }
        except Exception as e:
            log.warning(f"Erro Gemini (tentativa {attempt}): {e}")
            
    return default_res


def gerar_previa_legenda(title):
    """Gera uma prévia de 2 frases que gera curiosidade SEM revelar o desfecho da notícia."""
    if not GEMINI_KEY:
        return f"Uma situação impressionante está chamando a atenção de todo o Brasil. Você precisa ver o que aconteceu..."
    
    for attempt in range(3):
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GEMINI_KEY}"
            prompt = (
                f"Notícia: \"{title}\"\n"
                f"Escreva EXATAMENTE 2 frases em português do Brasil para legenda de post no Facebook.\n"
                f"REGRAS OBRIGATÓRIAS:\n"
                f"1. NÃO revele o resultado/desfecho da notícia.\n"
                f"2. Crie SUSPENSE e CURIOSIDADE para o leitor querer clicar no link.\n"
                f"3. Use linguagem informal, impactante e envolvente.\n"
                f"4. Termine a segunda frase com reticências (...) para deixar em aberto.\n"
                f"5. NÃO use hashtags, emojis ou o link. Apenas as 2 frases de texto.\n"
                f"6. Máximo 30 palavras no total.\n"
                f"Retorne APENAS as 2 frases, sem explicações."
            )
            payload = {"contents":[{"parts":[{"text":prompt}]}]}
            r = requests.post(url, json=payload, timeout=60)
            r.raise_for_status()
            previa = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            if previa:
                return previa
        except Exception as e:
            log.warning(f"Erro ao gerar prévia (tentativa {attempt}): {e}")
    
    return "Uma situação que ninguém esperava está sacudindo o Brasil. O que aconteceu vai te deixar de queixo caído..."

def gerar_video_ffmpeg(img_path, audio_path, output_path, duration=10):
    """
    Cria um vídeo de 'duration' segundos a partir de uma imagem e um áudio (looper).
    """
    log.info(f"🎞️ Gerando vídeo de {duration}s com FFmpeg...")
    try:
        # Comando: loop da imagem por X segundos, loop do áudio se necessário, codec compatível com Reels
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-t", str(duration), "-i", img_path,
            "-stream_loop", "-1", "-i", audio_path,
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-t", str(duration),
            output_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        log.info(f"✅ Vídeo gerado: {output_path}")
        return True
    except Exception as e:
        log.error(f"❌ Erro no FFmpeg: {e}")
        return False

def publicar_reel(page_id, token, video_path, message):
    """
    Publica um Reel no Facebook usando o processo de 3 etapas (Start, Upload, Finish).
    """
    log.info("🚀 Iniciando upload de Reel...")
    
    # 1. Start Upload Session
    try:
        url_init = f"https://graph.facebook.com/v22.0/{page_id}/video_reels"
        res_init = requests.post(url_init, params={
            "upload_phase": "start",
            "access_token": token
        }, timeout=30).json()
        
        video_id = res_init.get("video_id")
        if not video_id:
            log.error(f"Erro ao iniciar sessão Reel: {res_init}")
            return None
            
        # 2. Upload the Video
        file_size = os.path.getsize(video_path)
        url_upload = f"https://rupload.facebook.com/video-upload/v22.0/{video_id}"
        headers = {
            "Authorization": f"OAuth {token}",
            "offset": "0",
            "file_size": str(file_size),
            "Content-Type": "application/octet-stream"
        }
        with open(video_path, "rb") as f:
            res_up = requests.post(url_upload, headers=headers, data=f, timeout=120)
            
        if res_up.status_code != 200:
            log.error(f"Erro no upload binário: {res_up.text}")
            return None
            
        # 3. Finish and Publish
        url_finish = f"https://graph.facebook.com/v22.0/{page_id}/video_reels"
        payload = {
            "upload_phase": "finish",
            "video_id": video_id,
            "video_state": "PUBLISHED",
            "description": message,
            "access_token": token
        }
        res_finish = requests.post(url_finish, data=payload, timeout=30).json()
        
        if res_finish.get("success"):
            log.info(f"✅ REEL PUBLICADO! ID: {video_id}")
            return video_id
        else:
            log.error(f"Erro ao finalizar Reel: {res_finish}")
            return None
            
    except Exception as e:
        log.error(f"Erro no processo de publicação de Reel: {e}")
        return None

def adicionar_texto_premium(img_bytes, dados_esteticos):
    # dados_esteticos = {"hook", "tag", "color", "emoji", "reactions", "category"}
    MAIN_COLOR = dados_esteticos["color"]
    texto = dados_esteticos["hook"]
    tag_texto = dados_esteticos["tag"]
    emoji_hex = dados_esteticos["emoji"]
    reactions = dados_esteticos.get("reactions", [])  # lista de (hex, label)

    img = Image.open(BytesIO(img_bytes)).convert("RGB")
    w, h = img.size

    # --- ETAPA 3: FORMATO 9:16 (1080x1920) COM FUNDO PRETO ---
    sf = 2
    target_w, target_h = 1080, 1920
    bw, bh = target_w * sf, target_h * sf  # Supersampling 2x = 2160x3840

    # Crop quadrado da imagem original
    side = min(w, h)
    left = (w - side) / 2
    top = (h - side) / 2
    img_sq = img.crop((left, top, left + side, top + side))

    # Redimensionar imagem para largura total do canvas
    img_w_scaled = bw
    img_h_scaled = bw  # mantém 1:1
    img_hd = img_sq.resize((img_w_scaled, img_h_scaled), Image.Resampling.LANCZOS)
    img_hd = ImageEnhance.Color(img_hd).enhance(1.3)
    img_hd = ImageEnhance.Contrast(img_hd).enhance(1.1)
    img_hd = ImageEnhance.Sharpness(img_hd).enhance(1.4)

    # Tela preta 9:16
    canvas = Image.new("RGBA", (bw, bh), (0, 0, 0, 255))

    # Posicionar a imagem centralizada verticalmente
    img_y_offset = (bh - img_h_scaled) // 2
    canvas.paste(img_hd.convert("RGBA"), (0, img_y_offset))

    # Gradiente escuro apenas sobre a imagem (na região central)
    overlay = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)
    # Gradiente da metade inferior da imagem até o fim
    grad_start = img_y_offset + img_h_scaled // 2
    grad_end = img_y_offset + img_h_scaled
    grad_range = grad_end - grad_start
    for y in range(grad_start, grad_end):
        alpha = int(230 * ((y - grad_start) / grad_range))
        draw_ov.line([(0, y), (bw, y)], fill=(0, 0, 0, max(0, min(255, alpha))))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=5 * sf))
    canvas = Image.alpha_composite(canvas, overlay)

    draw_hd = ImageDraw.Draw(canvas)
    font_path = baixar_fonte()

    # 3. Selo Dinâmico Premium (topo da imagem)
    badge_h = int(bh * 0.035)
    f_badge = ImageFont.truetype(font_path, int(badge_h * 0.75)) if font_path else ImageFont.load_default()
    txt_badge = tag_texto
    bbox_b = draw_hd.textbbox((0, 0), txt_badge, font=f_badge)
    badge_w = (bbox_b[2] - bbox_b[0]) + (40 * sf)
    bx1, by1 = 30 * sf, img_y_offset + 40 * sf
    bx2, by2 = bx1 + badge_w, by1 + badge_h
    draw_hd.rectangle([bx1, by1, bx2, by2], fill=MAIN_COLOR)
    draw_hd.text(((bx1 + bx2) // 2, (by1 + by2) // 2), txt_badge, font=f_badge, fill=(255, 255, 255), anchor="mm")

    # 4. Título (HOOK) — posicionado na faixa preta inferior
    texto_puro = limpar_emojis(texto)
    f_size = int(bh * 0.075)
    font = ImageFont.truetype(font_path, f_size) if font_path else ImageFont.load_default()

    l = texto_puro.strip()
    bb = draw_hd.textbbox((0, 0), l, font=font)
    lw, lh = bb[2] - bb[0], bb[3] - bb[1]

    if lw > (bw - 100 * sf):
        f_size = int(f_size * (bw - 100 * sf) / lw)
        font = ImageFont.truetype(font_path, f_size) if font_path else ImageFont.load_default()
        bb = draw_hd.textbbox((0, 0), l, font=font)
        lw, lh = bb[2] - bb[0], bb[3] - bb[1]

    tx = (bw - lw) // 2
    padding = 35 * sf

    # Área abaixo da imagem: img_y_offset + img_h_scaled até bh
    area_inferior_inicio = img_y_offset + img_h_scaled
    area_inferior_altura = bh - area_inferior_inicio

    # Posição vertical do título: 1/3 da área inferior
    ty = area_inferior_inicio + int(area_inferior_altura * 0.20)

    # 5. Fundo do Título (Box)
    tx1, ty1 = tx - padding, ty - padding
    tx2, ty2 = tx + lw + padding, ty + lh + padding
    temp_box = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    draw_box = ImageDraw.Draw(temp_box)
    draw_box.rectangle([tx1, ty1, tx2, ty2], fill=MAIN_COLOR)
    canvas = Image.alpha_composite(canvas, temp_box)

    cx_title, cy_title = (tx1 + tx2) // 2, (ty1 + ty2) // 2

    # Sombra texto
    shadow_layer = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow_layer)
    s_draw.text((cx_title + 4 * sf, cy_title + 4 * sf), l, font=font, fill=(0, 0, 0, 200), anchor="mm")
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=3 * sf))
    canvas = Image.alpha_composite(canvas, shadow_layer)

    draw_hd = ImageDraw.Draw(canvas)
    draw_hd.text((cx_title, cy_title), l, font=font, fill=(255, 255, 255), anchor="mm")

    # 6. Ícone PREMIUM (acima do título)
    try:
        emoji_url = f"https://raw.githubusercontent.com/iamcal/emoji-data/master/img-apple-160/{emoji_hex}.png"
        r_emoji = requests.get(emoji_url, timeout=10)
        if r_emoji.status_code == 200:
            emoji_img = Image.open(BytesIO(r_emoji.content)).convert("RGBA")
            e_size = int(f_size * 1.5)
            emoji_img = emoji_img.resize((e_size, e_size), Image.Resampling.LANCZOS)
            ix = (bw - e_size) // 2
            iy = ty1 - e_size - (15 * sf)
            e_shadow = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
            ImageDraw.Draw(e_shadow).ellipse(
                [ix + 8 * sf, iy + 8 * sf, ix + e_size + 8 * sf, iy + e_size + 8 * sf],
                fill=(0, 0, 0, 150)
            )
            e_shadow = e_shadow.filter(ImageFilter.GaussianBlur(radius=8 * sf))
            canvas = Image.alpha_composite(canvas, e_shadow)
            canvas.paste(emoji_img, (ix, iy), emoji_img)
    except Exception as e:
        log.warning(f"Erro ao carregar emoji principal: {e}")

    draw_hd = ImageDraw.Draw(canvas)

    # 7. ETAPA 4 — Emojis de reação do Facebook abaixo do título (exceto CRIME)
    if reactions:
        reaction_y = ty2 + int(30 * sf)  # começa logo abaixo do box do título
        r_emoji_size = int(f_size * 0.85)
        f_react_size = int(badge_h * 0.65)
        f_react = ImageFont.truetype(font_path, f_react_size) if font_path else ImageFont.load_default()

        # Calcular largura total do bloco de reações para centralizar
        gap = int(20 * sf)
        total_block_w = len(reactions) * (r_emoji_size + gap + int(draw_hd.textbbox((0,0), reactions[0][1], font=f_react)[2])) - gap

        rx_start = (bw - total_block_w) // 2
        rx = rx_start

        for (r_hex, r_label) in reactions:
            try:
                r_url = f"https://raw.githubusercontent.com/iamcal/emoji-data/master/img-facebook-96/{r_hex}.png"
                r_resp = requests.get(r_url, timeout=10)
                if r_resp.status_code != 200:
                    # Fallback para apple
                    r_url = f"https://raw.githubusercontent.com/iamcal/emoji-data/master/img-apple-160/{r_hex}.png"
                    r_resp = requests.get(r_url, timeout=10)
                if r_resp.status_code == 200:
                    r_img = Image.open(BytesIO(r_resp.content)).convert("RGBA")
                    r_img = r_img.resize((r_emoji_size, r_emoji_size), Image.Resampling.LANCZOS)
                    ry = reaction_y
                    canvas.paste(r_img, (rx, ry), r_img)
                    # Label abaixo do emoji
                    draw_hd = ImageDraw.Draw(canvas)
                    lbb = draw_hd.textbbox((0, 0), r_label, font=f_react)
                    lw_r = lbb[2] - lbb[0]
                    lx = rx + (r_emoji_size - lw_r) // 2
                    ly = ry + r_emoji_size + int(5 * sf)
                    # Sombra do label
                    draw_hd.text((lx + 2, ly + 2), r_label, font=f_react, fill=(0, 0, 0, 200))
                    draw_hd.text((lx, ly), r_label, font=f_react, fill=(255, 255, 255))
                    rx += r_emoji_size + int(draw_hd.textbbox((0,0), r_label, font=f_react)[2]) + gap
            except Exception as e_r:
                log.warning(f"Erro ao carregar emoji reação {r_hex}: {e_r}")

    # 8. CTA na base
    f_sub_size = int(badge_h * 0.75)
    f_sub = ImageFont.truetype(font_path, f_sub_size) if font_path else ImageFont.load_default()
    cta_t = 'Clique em "...mais" para ver na íntegra'
    draw_hd = ImageDraw.Draw(canvas)
    bw_cta = draw_hd.textbbox((0, 0), cta_t, font=f_sub)
    cta_x = (bw - (bw_cta[2] - bw_cta[0])) // 2
    cta_y = bh - int(80 * sf)
    cta_shadow = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    ImageDraw.Draw(cta_shadow).text((cta_x + 2 * sf, cta_y + 2 * sf), cta_t, font=f_sub, fill=(0, 0, 0, 220))
    cta_shadow = cta_shadow.filter(ImageFilter.GaussianBlur(radius=2 * sf))
    canvas = Image.alpha_composite(canvas, cta_shadow)
    draw_hd = ImageDraw.Draw(canvas)
    draw_hd.text((cta_x, cta_y), cta_t, font=f_sub, fill=(255, 215, 0))

    # --- FINALIZAÇÃO: REDUÇÃO PARA 1080x1920 ---
    final_img = canvas.resize((target_w, target_h), Image.Resampling.LANCZOS).convert("RGB")
    out = BytesIO()
    final_img.save(out, format="JPEG", quality=98)
    return out.getvalue()

def get_noticias():
    from playwright.sync_api import sync_playwright
    res = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            log.info("Acessando SFY...")
            page.goto(SFY_LOGIN)
            page.fill("input[name='email']", SFY_EMAIL)
            page.fill("input[name='password']", SFY_PASSWORD)
            page.click("button[type='submit']")
            page.wait_for_url("**/dashboard**", timeout=40000)
            page.goto(SFY_SHARE)
            page.wait_for_timeout(7000)
            
            log.info("Selecionando bloco Sharesforyou...")
            try:
                page.click("button.change-order-by:has-text('Sharesforyou')", timeout=15000)
                page.wait_for_timeout(10000)
            except Exception as e:
                log.warning(f"Não foi possível clicar no botão Sharesforyou (pode já estar selecionado): {e}")

            cards = page.locator(".card").all()
            log.info(f"Encontrados {len(cards)} cards no bloco Sharesforyou.")
            
            for card in cards:
                try:
                    title = card.locator("h5, p.fs-4").first.inner_text().strip()
                    link = card.locator("a:has(i.ti-eye)").first.get_attribute("href")
                    img = card.locator("img").first.get_attribute("src")
                    if link and title:
                        if link.startswith("/"): link = "https://www.sharesforyou.com" + link
                        if img and img.startswith("/"): img = "https://www.sharesforyou.com" + img
                        
                        # FIX 403: baixar imagem dentro da sessão autenticada do Playwright
                        img_bytes = None
                        if img:
                            try:
                                resp = page.request.get(img)
                                if resp.status == 200:
                                    img_bytes = resp.body()
                                    log.info(f"🖼️ Imagem baixada via Playwright ({len(img_bytes)//1024}KB)")
                                else:
                                    log.warning(f"⚠️ Status imagem: {resp.status} para {img}")
                            except Exception as e_img:
                                log.warning(f"⚠️ Erro baixando imagem via Playwright: {e_img}")
                        
                        res.append({"id": make_article_id(link), "title": title, "link": link, "img": img, "img_bytes": img_bytes})
                except: continue
        except Exception as e: log.error(f"Erro Playwright: {e}")
        finally: browser.close()
    return res

def main():
    log.info("Bot Profissional Notícias Iniciado.")
    
    # Ler tokens diretamente das variáveis de ambiente (padrão do GitHub Actions)
    load_dotenv(override=True)
    FB_PAGE_ID = os.environ.get("FB_PAGE_ID", "").strip()
    FB_TOKEN   = os.environ.get("FB_TOKEN", "").strip()
    
    if not FB_TOKEN or not FB_PAGE_ID:
        log.error("❌ FB_TOKEN ou FB_PAGE_ID não configurados. Encerrando.")
        return
    
    log.info(f"🔑 PAGE_ID: {FB_PAGE_ID}")
    log.info(f"🔑 TOKEN: {FB_TOKEN[:20]}...")

    posted = load_posted()
    news = get_noticias()
    if not news:
        log.warning("Nenhuma notícia encontrada.")
        return
    
    for n in news:
        if n["id"] in posted:
            log.info(f"⏭️ Pulando: {n['title'][:50]}... (Já postado)")
            continue
        try:
            # Usar bytes baixados via Playwright (evita 403) ou fallback por URL
            img_data = n.get("img_bytes")
            if img_data is None:
                if not n.get("img"):
                    log.warning(f"⚠️ Sem imagem para: {n['title'][:50]}")
                    continue
                r_img = requests.get(n["img"], headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
                if r_img.status_code != 200:
                    log.warning(f"⚠️ Imagem retornou {r_img.status_code}, pulando.")
                    continue
                img_data = r_img.content
            
            estetica = gerar_gancho(n["title"])
            img_b = adicionar_texto_premium(img_data, estetica)
            
            # Salvar imagem temporária para o FFmpeg
            temp_img = "temp_post.jpg"
            with open(temp_img, "wb") as f:
                f.write(img_b)
            
            # Selecionar áudio aleatório
            audio_files = glob.glob("AUDIOS NEWS/*.mp3")
            if not audio_files:
                log.error("❌ Nenhum arquivo MP3 encontrado na pasta AUDIOS NEWS!")
                continue
            
            audio_sel = random.choice(audio_files)
            temp_video = "temp_reel.mp4"
            
            if not gerar_video_ffmpeg(temp_img, audio_sel, temp_video):
                continue
            
            
            padding = "\n.\n.\n.\n.\n.\n"
            hashtags = estetica.get("hashtags", "#noticias #brasil").lower()
            previa = gerar_previa_legenda(n["title"])
            msg = f"😱 {n['title'].upper()} 😱\n\n{previa}\n\n{hashtags}{padding}🔗VEJA MAIS NO LINK: {n['link']}"
            
            video_id = publicar_reel(FB_PAGE_ID, FB_TOKEN, temp_video, msg)
            
            if video_id:
                log.info(f"🔗 LINK REEL: https://www.facebook.com/reels/{video_id}/")
                posted.add(n["id"])
                save_posted(posted)
                
                # Limpeza
                for f in [temp_img, temp_video]:
                    if os.path.exists(f): os.remove(f)
                break
            else:
                log.error("Falha ao publicar Reel.")
                if os.path.exists(temp_img): os.remove(temp_img)
                if os.path.exists(temp_video): os.remove(temp_video)
        except Exception as e: 
            log.error(f"Erro no loop principal: {e}")
            log.error(traceback.format_exc())

if __name__ == "__main__": main()
