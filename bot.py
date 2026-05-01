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
import difflib

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

# Palavras irrelevantes para normalização semântica de títulos
_STOP_WORDS = {
    "de","da","do","das","dos","a","o","as","os","e","em","no","na","nos","nas",
    "por","para","com","que","se","ao","à","um","uma","uns","umas","é","foi",
    "ser","ter","mais","mas","ou","ele","ela","eles","elas","seu","sua"
}

def normalizar_titulo(title):
    """Normaliza título removendo stop words, números e pontuação para comparação semântica."""
    t = title.lower()
    t = re.sub(r'[^\w\s]', '', t)          # Remove pontuação
    t = re.sub(r'\b\d+\b', '', t)          # Remove números isolados
    palavras = [w for w in t.split() if w not in _STOP_WORDS and len(w) > 2]
    return ' '.join(sorted(palavras))       # Ordena para capturar rearranjos de palavras

def make_article_id(title):
    """Gera ID estável baseado no título normalizado — imune a variações de pontuação/capitalização."""
    chave = normalizar_titulo(title)
    return hashlib.sha256(chave.encode('utf-8')).hexdigest()[:16]

def load_state():
    """
    Carrega o estado unificado do bot a partir do posted_ids.json.
    Retorna (set_de_ids, lista_de_titulos_recentes).
    Suporta tanto o formato legado (lista de IDs) quanto o novo formato (dict com ids + titles).
    """
    if not os.path.exists(POSTED_FILE):
        return set(), []
    try:
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Formato legado: lista de strings
        if isinstance(data, list):
            log.info(f"📂 Estado legado carregado: {len(data)} IDs. Migrando para novo formato.")
            return set(data), []
        # Novo formato: dicionário
        if isinstance(data, dict):
            ids = set(data.get("ids", []))
            titles = data.get("titles", [])
            log.info(f"📂 Estado carregado: {len(ids)} IDs únicos | {len(titles)} títulos recentes.")
            return ids, titles
    except Exception as e:
        log.warning(f"⚠️ Erro ao carregar estado: {e}")
    return set(), []

def save_state(ids_set, titles_list):
    """Salva o estado unificado em formato JSON estruturado."""
    # Mantém os últimos 200 títulos para o fuzzy match (sem crescer indefinidamente)
    titles_list = titles_list[-200:]
    data = {
        "ids": sorted(list(ids_set)),
        "titles": titles_list
    }
    try:
        with open(POSTED_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log.info(f"💾 Estado salvo: {len(ids_set)} IDs | {len(titles_list)} títulos.")
    except Exception as e:
        log.error(f"❌ Falha ao salvar estado: {e}")

def load_recent_titles():
    """Carrega títulos recentes para o Gemini não repetir HOOKs visuais."""
    if os.path.exists("last_title.txt"):
        try:
            with open("last_title.txt", "r", encoding="utf-8") as f:
                return [linha.strip() for linha in f.readlines() if linha.strip()]
        except: return []
    return []

def save_recent_titles(titles_list):
    try:
        with open("last_title.txt", "w", encoding="utf-8") as f:
            for t in titles_list[-15:]:
                f.write(t + "\n")
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

# Mapeamento de emojis de reação do Facebook
FB_REACTIONS = {
    "LIKE": "1f44d",
    "LOVE": "2764-fe0f",
    "CARE": "1f917",
    "HAHA": "1f606",
    "WOW": "1f62e",
    "SAD": "1f622",
    "ANGRY": "1f621"
}

def gerar_gancho(title):
    default_res = {
        "hook": "REVELAÇÃO CHOCANTE!", "tag": "NOTÍCIA URGENTE",
        "color": (255, 0, 0, 200), "emoji": "1f6a8",
        "hashtags": "#noticias #urgente",
        "category": "URGENTE",
        "reactions": [("1f631", "Absurdo!"), ("1f622", "Que triste"), ("1f621", "Indignado")]
    }
    if not GEMINI_KEY: return default_res
    
    recent_titles = load_recent_titles()
    recent_str = ", ".join([f'"{t}"' for t in recent_titles]) if recent_titles else "Nenhum"
    
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
                f"Retorne APENAS uma linha no formato: HOOK | CATEGORY | EMOJI | HASHTAGS | R1:L1 | R2:L2 | R3:L3\n"
                f"- HOOK: Título EXTREMAMENTE CURTO (MÁXIMO 3 PALAVRAS) em MAIÚSCULAS.\n"
                f"  REGRA DE CAMUFLAGEM: substitua letras por numeros/simbolos SOMENTE se o HOOK\n"
                f"  contiver EXATAMENTE uma destas palavras proibidas:\n"
                f"  MORTE, MORTO, MORREU, MATAR, MATOU, MATARAM, ASSASSINOU, ASSASSINATO,\n"
                f"  ESPANCOU, SANGUE, TIRO, TIROS, BALEADO, ESTUPRO, ESTUPROU, ABUSO,\n"
                f"  TRAFICO, DROGA, DROGAS, COCAINA, CRACK.\n"
                f"  Exemplos CORRETOS: MORTE->M0RT3, MATOU->M@T0U, TIRO->T1R0, SANGUE->S@NGU3, ESTUPRO->3STUPR0.\n"
                f"  PROIBIDO substituir letras em qualquer outra palavra.\n"
                f"- CATEGORY: Escolha exatamente uma: URGENTE, POLITICA, ESPORTE, FOFOCA, CRIME.\n"
                f"- EMOJI: UM único emoji que combine com o tema.\n"
                f"- HASHTAGS: Liste de 3 a 5 hashtags de SEO separadas por espaço, TODAS EM MINÚSCULAS.\n"
                f"- R1, R2, R3: Tipo de reação (LIKE, LOVE, CARE, HAHA, WOW, SAD, ANGRY).\n"
                f"Não retorne opiniões repetidas, varie sempre.\n"
                f"PROIBIDO REPETIR QUALQUER UM DESTES ÚLTIMOS HOOKS GERADOS: {recent_str}."
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
                    
                    if hook not in recent_titles:
                        recent_titles.append(hook)
                        save_recent_titles(recent_titles)
                        
                        config = CATEGORIES.get(cat_key, CATEGORIES["URGENTE"])
                        emoji_hex = EMOJI_HEX.get(emoji_char, "1f525")
                        
                        reactions = []
                        # Parsear as reações (R:L) das partes 4, 5 e 6
                        for i in range(4, 7):
                            if i < len(parts) and ":" in parts[i]:
                                r_type, r_label = parts[i].split(":", 1)
                                r_type = r_type.strip().upper()
                                r_label = r_label.strip()
                                if r_type in FB_REACTIONS:
                                    reactions.append((FB_REACTIONS[r_type], r_label))
                        
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
            log.warning(f"Erro ao gerar título misterioso (tentativa {attempt}): {e}")
    
    return "O QUE ACONTECEU VAI TE DEIXAR DE QUEIXO CAÍDO"

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
    reactions = dados_esteticos.get("reactions", [])

    img = Image.open(BytesIO(img_bytes)).convert("RGB")
    w, h = img.size

    # --- CONFIGURAÇÃO SUPERSAMPLING (2x para 1080x1080 interno) ---
    sf = 2
    base_side = 1080
    bw = bh = base_side * sf

    # 1. Crop quadrado da imagem original
    side = min(w, h)
    left = (w - side) / 2
    top = (h - side) / 2
    img_sq = img.crop((left, top, left + side, top + side))
    
    # 2. Redimensionamento e Melhoria da imagem base (1:1)
    img_core = img_sq.resize((bw, bh), Image.Resampling.LANCZOS)
    img_core = ImageEnhance.Color(img_core).enhance(1.3)
    img_core = ImageEnhance.Contrast(img_core).enhance(1.1)
    img_core = ImageEnhance.Sharpness(img_core).enhance(1.4)

    # 3. Gradiente de base (escurecer parte inferior para leitura do título)
    overlay = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)
    grad_h = int(bh * 0.50)
    for y in range(bh - grad_h, bh):
        alpha = int(240 * ((y - (bh - grad_h)) / grad_h))
        draw_ov.line([(0, y), (bw, y)], fill=(0, 0, 0, max(0, min(255, alpha))))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=5 * sf))
    img_core = Image.alpha_composite(img_core.convert("RGBA"), overlay)
    
    draw_core = ImageDraw.Draw(img_core)
    font_path = baixar_fonte()

    # 4. Selo de Categoria (Topo)
    badge_h = int(bh * 0.05)
    f_badge = ImageFont.truetype(font_path, int(badge_h * 0.75)) if font_path else ImageFont.load_default()
    bbox_b = draw_core.textbbox((0, 0), tag_texto, font=f_badge)
    badge_w = (bbox_b[2] - bbox_b[0]) + (40 * sf)
    bx1, by1 = 30 * sf, 40 * sf
    bx2, by2 = bx1 + badge_w, by1 + badge_h
    draw_core.rectangle([bx1, by1, bx2, by2], fill=MAIN_COLOR)
    draw_core.text(((bx1 + bx2) // 2, (by1 + by2) // 2), tag_texto, font=f_badge, fill=(255, 255, 255), anchor="mm")

    # 5. Título (HOOK) — posicionado na parte inferior do 1:1
    texto_puro = limpar_emojis(texto)
    f_size = int(bh * 0.10)
    font = ImageFont.truetype(font_path, f_size) if font_path else ImageFont.load_default()

    l = texto_puro.strip()
    bb = draw_core.textbbox((0, 0), l, font=font)
    lw, lh = bb[2] - bb[0], bb[3] - bb[1]

    if lw > (bw - 100 * sf):
        f_size = int(f_size * (bw - 100 * sf) / lw)
        font = ImageFont.truetype(font_path, f_size) if font_path else ImageFont.load_default()
        bb = draw_core.textbbox((0, 0), l, font=font)
        lw, lh = bb[2] - bb[0], bb[3] - bb[1]

    tx = (bw - lw) // 2
    padding = 35 * sf
    ty = int(bh * 0.85) - lh # Posicionado no terço inferior do quadrado

    # Fundo do Título (Box)
    tx1, ty1 = tx - padding, ty - padding
    tx2, ty2 = tx + lw + padding, ty + lh + padding
    temp_box = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    ImageDraw.Draw(temp_box).rectangle([tx1, ty1, tx2, ty2], fill=MAIN_COLOR)
    img_core = Image.alpha_composite(img_core, temp_box)

    # SOMBRA DO TÍTULO
    cx, cy = (tx1 + tx2) // 2, (ty1 + ty2) // 2
    shadow_layer = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow_layer)
    s_draw.text((cx + 4 * sf, cy + 4 * sf), l, font=font, fill=(0, 0, 0, 200), anchor="mm")
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=3 * sf))
    img_core = Image.alpha_composite(img_core, shadow_layer)

    # Texto do Título
    draw_core = ImageDraw.Draw(img_core)
    draw_core.text((cx, cy), l, font=font, fill=(255, 255, 255), anchor="mm")

    # 6. Ícone Principal (acima do título)
    try:
        emoji_url = f"https://raw.githubusercontent.com/iamcal/emoji-data/master/img-apple-160/{emoji_hex}.png"
        r_emoji = requests.get(emoji_url, timeout=10)
        if r_emoji.status_code == 200:
            e_img = Image.open(BytesIO(r_emoji.content)).convert("RGBA")
            e_size = int(f_size * 1.5)
            e_img = e_img.resize((e_size, e_size), Image.Resampling.LANCZOS)
            ix, iy = (bw - e_size) // 2, ty1 - e_size - (2 * sf)
            
            # Sombra do Ícone Principal
            e_shadow = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
            ImageDraw.Draw(e_shadow).ellipse(
                [ix + 6*sf, iy + 6*sf, ix + e_size + 6*sf, iy + e_size + 6*sf],
                fill=(0, 0, 0, 150)
            )
            e_shadow = e_shadow.filter(ImageFilter.GaussianBlur(radius=6*sf))
            img_core = Image.alpha_composite(img_core, e_shadow)
            
            img_core.paste(e_img, (ix, iy), e_img)
    except: pass

    # 7. Emojis de Reação (Opinião ao lado direito)
    if reactions:
        # Posição: um pouco abaixo do título, dentro do quadrado 1:1
        react_y = ty2 + int(55 * sf) # Ainda mais para baixo
        r_emoji_size = int(f_size * 0.51) # +20% de redução (era 0.64)
        f_react_size = int(badge_h * 0.48) # +20% de redução (era 0.6)
        f_react = ImageFont.truetype(font_path, f_react_size) if font_path else ImageFont.load_default()

        # Calcular largura total do bloco de reações (Emoji + Espaço + Texto + Gap)
        gap_entre_blocos = int(35 * sf)
        espacinho = int(12 * sf)
        total_w = 0
        blocos = []
        
        for (r_hex, r_label) in reactions:
            lbb = draw_core.textbbox((0, 0), r_label, font=f_react)
            lw_r = lbb[2] - lbb[0]
            bloco_w = r_emoji_size + espacinho + lw_r
            blocos.append({"hex": r_hex, "label": r_label, "w": bloco_w, "text_w": lw_r})
            total_w += bloco_w
        
        total_w += gap_entre_blocos * (len(reactions) - 1)
        rx = (bw - total_w) // 2

        for b in blocos:
            try:
                r_url = f"https://raw.githubusercontent.com/iamcal/emoji-data/master/img-facebook-96/{b['hex']}.png"
                r_resp = requests.get(r_url, timeout=10)
                if r_resp.status_code != 200:
                    r_url = f"https://raw.githubusercontent.com/iamcal/emoji-data/master/img-apple-160/{b['hex']}.png"
                    r_resp = requests.get(r_url, timeout=10)
                
                if r_resp.status_code == 200:
                    ri = Image.open(BytesIO(r_resp.content)).convert("RGBA")
                    ri = ri.resize((r_emoji_size, r_emoji_size), Image.Resampling.LANCZOS)
                    # Centralizar emoji verticalmente em relação ao texto se necessário, ou usar react_y
                    img_core.paste(ri, (rx, react_y), ri)
                    
                    # Texto ao lado direito (com leve sombra)
                    tx_pos = rx + r_emoji_size + espacinho
                    ty_pos = react_y + (r_emoji_size // 2)
                    draw_core = ImageDraw.Draw(img_core)
                    draw_core.text((tx_pos + 1*sf, ty_pos + 1*sf), b["label"], font=f_react, fill=(0, 0, 0, 180), anchor="lm")
                    draw_core.text((tx_pos, ty_pos), b["label"], font=f_react, fill=(255, 255, 255), anchor="lm")
                    
                    rx += b["w"] + gap_entre_blocos
            except: pass

    # --- ETAPA FINAL: COMPOSIÇÃO COM FUNDO BLURRED 9:16 ---
    target_w, target_h = 1080, 1920
    tw_sf, th_sf = target_w * sf, target_h * sf
    
    # Criar fundo: Redimensionar o quadrado para preencher o 9:16 (aspect fill)
    # Como img_core é quadrado, redimensionamos para th_sf x th_sf e cortamos as laterais
    bg_size = th_sf
    background = img_core.resize((bg_size, bg_size), Image.Resampling.LANCZOS)
    
    # Cortar o centro para ficar 1080x1920 (tw_sf x th_sf)
    left = (bg_size - tw_sf) // 2
    background = background.crop((left, 0, left + tw_sf, th_sf))
    
    # Aplicar Blur e escurecer para que o conteúdo original ganhe destaque
    background = background.filter(ImageFilter.GaussianBlur(radius=20 * sf))
    background = ImageEnhance.Brightness(background).enhance(0.55)
    
    canvas_916 = background
    
    # Colar o conteúdo nítido e original no centro vertical
    y_offset = (th_sf - bh) // 2
    canvas_916.paste(img_core.convert("RGBA"), (0, y_offset), img_core.convert("RGBA"))
    
    # Finalização
    final_img = canvas_916.resize((target_w, target_h), Image.Resampling.LANCZOS).convert("RGB")
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
                        
                        res.append({"id": make_article_id(title), "title": title, "link": link, "img": img, "img_bytes": img_bytes})
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

    posted_ids, posted_titles = load_state()
    news = get_noticias()
    if not news:
        log.warning("Nenhuma notícia encontrada.")
        return
    
    log.info(f"📰 {len(news)} notícias encontradas. Verificando duplicatas...")
    n_puladas = 0
    
    for n in news:
        # --- CAMADA 1: Hash exato pelo ID (título normalizado) ---
        if n["id"] in posted_ids:
            log.info(f"⏭️ [ID] Pulando: {n['title'][:60]}")
            n_puladas += 1
            continue
        
        # --- CAMADA 2: Fuzzy match semântico contra os últimos 200 títulos ---
        titulo_norm = normalizar_titulo(n["title"])
        similaridade_encontrada = False
        melhor_match = 0.0
        
        for titulo_hist in posted_titles:
            ratio = difflib.SequenceMatcher(None, titulo_norm, titulo_hist).ratio()
            if ratio > melhor_match:
                melhor_match = ratio
            # Threshold de 0.80 — equilibrado: pega reescritas, permite notícias diferentes
            if ratio >= 0.80:
                similaridade_encontrada = True
                log.info(f"⏭️ [Fuzzy {ratio*100:.1f}%] Pulando: {n['title'][:60]}")
                break
        
        if not similaridade_encontrada and melhor_match > 0:
            log.info(f"  ✅ Mais parecida encontrada: {melhor_match*100:.1f}% — permitida.")
        
        if similaridade_encontrada:
            n_puladas += 1
            continue
        
        log.info(f"🆕 Notícia inédita encontrada: {n['title'][:60]}")
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
            duracao_random = random.randint(20, 30)
            
            if not gerar_video_ffmpeg(temp_img, audio_sel, temp_video, duration=duracao_random):
                continue
            
            
            hashtags = estetica.get("hashtags", "#noticias #brasil").lower()
            misterio = gerar_titulo_misterioso(n["title"])
            
            # Formatação solicitada: 
            # 😱 TAG: MISTERIO... 😱
            # .
            # #hashtags
            # .
            # .
            # .
            # 🔗VEJA MAIS NO LINK: URL
            
            padding_bottom = "\n.\n.\n.\n"
            msg = f"😱 {estetica['tag'].upper()}: {misterio}... 😱\n.\n{hashtags}{padding_bottom}🔗VEJA MAIS NO LINK: {n['link']}"
            
            video_id = publicar_reel(FB_PAGE_ID, FB_TOKEN, temp_video, msg)
            
            if video_id:
                log.info(f"🔗 LINK REEL: https://www.facebook.com/reels/{video_id}/")
                
                # Registra o ID e o título normalizado para deduplicação futura
                posted_ids.add(n["id"])
                posted_titles.append(normalizar_titulo(n["title"]))
                save_state(posted_ids, posted_titles)
                
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
