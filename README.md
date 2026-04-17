# 🤖 Bot Notícias Face 02 - Reels Edition 🎬

Este é um bot de inteligência artificial de alta performance projetado para transformar notícias em **Facebook Reels (Vídeos Verticais 1:1)** de forma 100% autônoma. Ele opera na nuvem do GitHub Actions, eliminando a necessidade de manter um computador ligado.

---

## 🎯 Objetivo
Automatizar a presença digital em páginas de notícias, gerando engajamento através de Reels dinâmicos de 10 segundos, utilizando ganchos virais gerados por IA e áudios de suporte profissional.

## 🚀 Tecnologias e Ferramentas
- **Linguagem**: Python 3.11+
- **Motor de Scraping**: [Playwright](https://playwright.dev/) (para capturar notícias do SFY sem bloqueios).
- **Cérebro (IA)**: [Google Gemini Pro/Flash](https://ai.google.dev/) (gera títulos impactantes e hashtags de SEO).
- **Processamento de Imagem**: PIL (Pillow) para criar capas dinâmicas.
- **Motor de Vídeo**: [FFmpeg](https://ffmpeg.org/) (funde a imagem da notícia com áudios MP3 aleatórios).
- **Hospedagem**: [GitHub Actions](https://github.com/features/actions) (roda o bot por agendamento ou gatilho manual).
- **Publicação**: Facebook Reels Publishing API (Fluxo de 3 etapas: Inicialização, Upload e Finalização).

---

## 🧠 Lógica de Funcionamento

O bot segue um pipeline rigoroso de 6 etapas:

1.  **Scraping**: Acessa o portal SharesForYou, faz login e extrai as 17 notícias mais quentes do momento.
2.  **Filtro Antiduplicata**: Verifica o arquivo `posted_ids.json` para nunca postar a mesma notícia duas vezes.
3.  **Processamento por IA**: Envia o título e resumo para o **Google Gemini**, que retorna:
    - Um gancho (Hook) viral de no máximo 3 palavras para a capa.
    - Categorização automática (URGENTE, ESPORTE, FOFOCA, etc).
    - Camuflagem de palavras sensíveis (ex: M0RT3) para evitar "Shadowban".
4.  **Criação do Vídeo**:
    - Gera uma imagem quadrada (1080x1080) com a foto da notícia e a tag colorida.
    - Sorteia um áudio da pasta `AUDIOS NEWS`.
    - Usa o FFmpeg para criar um vídeo `.mp4` de exatos 10 segundos.
5.  **Publicação**: Faz o upload do vídeo para o Facebook via API de Reels, incluindo na legenda o link oficial da notícia para monetização.
6.  **Persistência**: Salva o ID da notícia postada e faz um `git push` automático para atualizar o histórico no repositório.

---

## 🛠️ Como criar um novo bot do zero (Replicação)

Se você quiser criar o **Bot 03, 04...**, siga este checklist:

### 1. Preparação do Repositório
- Clone este repositório ou crie um novo GitHub em branco.
- Envie os arquivos principais: `bot.py`, `requirements.txt`, e a pasta `AUDIOS NEWS`.

### 2. Configuração de Variáveis (Secrets)
No GitHub, vá em **Settings > Secrets and variables > Actions** e adicione:
- `FB_PAGE_ID`: O ID da página alvo.
- `FB_TOKEN`: O Token de acesso da página (permissão de Reels).
- `GEMINI_API_KEY`: Sua chave do Google AI.
- `SFY_EMAIL` / `SFY_PASSWORD`: Suas credenciais do portal SharesForYou.

### 3. Gatilho de Ativação (WAKE UP)
O bot está configurado para o modo **Manual/External**, controlado pelo **Google Apps Script**. Para que ele rode, você deve enviar um comando POST para a API do GitHub (conforme o script Google que fornecemos).

---

## 📁 Estrutura de Pastas
- `/AUDIOS NEWS`: Contém os áudios de fundo que o bot sorteia.
- `bot.py`: O coração do sistema.
- `diagnostico.py`: Utilitário para testar se as chaves e IDs estão corretos.
- `posted_ids.json`: Memória do robô sobre o que já foi publicado.
- `.github/workflows/facebook_news_bot.yml`: Configuração da máquina virtual na nuvem.

---

## 🛡️ Blindagem contra Erros
- **Auto-Sincronização**: O bot faz `pull --rebase` antes de cada push, evitando conflitos de versão.
- **IA Timeout**: Configurado para esperar até 60s por respostas lentas da API do Gemini.
- **Instalação Automática**: O servidor Linux instala FFmpeg e Playwright do zero em cada execução.

---
> **Criado por Antigravity AI**  
> *Transformando bits em engajamento digital.*
