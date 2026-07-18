# 📡 Radar Viral

Ferramenta interna para identificar vídeos em alta no TikTok por nicho, pontuá-los,
guardar os melhores candidatos e sugerir legendas de repost **sempre com crédito ao
criador original**.

## Regras da ferramenta

- Os vídeos são descarregados **com a marca de água original intacta** — o downloader
  grava o ficheiro tal como vem da API e nunca o processa, corta ou edita.
- Toda a legenda sugerida inclui o `@` do autor original (`🔥 via @autor · descrição`).
- A decisão de repostar é sempre manual, a partir do dashboard.
- A chave da RapidAPI vive apenas no `.env` (que está no `.gitignore`).

## Setup (Termux / proot Ubuntu)

```bash
# 1. Dependências
sudo apt update && sudo apt install -y python3 python3-pip python3-venv
git clone <este-repo> && cd Extrair

# 2. Ambiente virtual
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Chave da RapidAPI
cp .env.example .env
nano .env   # cola a tua chave em RAPIDAPI_KEY=...
```

A chave obtém-se em [rapidapi.com](https://rapidapi.com) subscrevendo um endpoint de
TikTok (por omissão o código espera o **tiktok-scraper7**, endpoint
`/challenge/posts`). Se usares outro endpoint, ajusta `RAPIDAPI_HOST` /
`RAPIDAPI_ENDPOINT` no `.env` e, se o formato da resposta for diferente, a função
`normalizar_item()` em `coletor.py`.

## Uso

### 1. Coletar vídeos de um nicho

```bash
python coletor.py --nicho barbearia                 # usa a hashtag "barbearia"
python coletor.py --nicho barbearia --hashtag barber --quantidade 30
python coletor.py --nicho barbearia --descarregar   # coleta + score + download dos candidatos
python coletor.py --nicho barbearia --mock          # dados de exemplo, sem gastar API
```

Cada coleta guarda os vídeos no SQLite (`radar_viral.db`), ignora duplicados
(chave única por `id` do vídeo) e recalcula automaticamente o score viral.

### 2. Score viral

```
score = (views / horas desde publicação) × (1 + PESO_ENGAGEMENT × engagement)
engagement = (likes + comentários + partilhas) / views
```

Vídeos com score ≥ `SCORE_THRESHOLD` (configurável no `.env`) ficam marcados como
**candidato**. Recalcular manualmente: `python score.py --nicho barbearia`.

### 3. Download dos candidatos

```bash
python downloader.py --nicho barbearia
```

Só descarrega candidatos (não todos os vídeos), para `downloads/{nicho}/{id}.mp4`,
mantendo a watermark, e gera a legenda sugerida com crédito.

### 4. Dashboard

```bash
python app.py
# abre http://127.0.0.1:5000
```

- Lista candidatos do dia/semana ordenados por score, com preview, métricas e legenda.
- Filtro por nicho e intervalo de datas.
- Botão **📋 Copiar legenda** (já com o crédito ao autor).
- Botão **✅ Marcar como usado** para não repetir sugestões (reversível).

## Agendar o coletor

**Opção A — cron** (proot Ubuntu com `cronie`/`cron` instalado):

```cron
# a cada 2 horas, coleta + download dos candidatos do nicho "barbearia"
0 */2 * * * cd /caminho/para/Extrair && .venv/bin/python coletor.py --nicho barbearia --descarregar >> coletor.log 2>&1
```

**Opção B — sem cron** (útil no Termux): o próprio coletor repete em loop:

```bash
python coletor.py --nicho barbearia --descarregar --agendar 120   # a cada 120 min
```

## Estrutura

```
app.py            # dashboard Flask
coletor.py        # coleta via RapidAPI (CLI + agendável)
score.py          # cálculo do score viral e marcação de candidatos
downloader.py     # download dos candidatos (com watermark) + legenda sugerida
db.py, config.py  # SQLite e configuração (.env)
coletor/          # dados de apoio do coletor (mock para testes)
downloads/        # vídeos descarregados por nicho (ignorado no git)
templates/        # HTML do dashboard (Tailwind via CDN)
static/           # assets estáticos
.env.example      # modelo de configuração — copiar para .env
```

## Testar sem chave da API

```bash
python coletor.py --nicho barbearia --mock
python app.py
```

O modo `--mock` usa `coletor/mock_videos.json` para simular a resposta da API e
validar todo o fluxo (coleta → score → dashboard).
