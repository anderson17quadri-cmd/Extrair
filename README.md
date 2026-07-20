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

A chave obtém-se em [rapidapi.com](https://rapidapi.com) subscrevendo a API
**tiktok-scraper7** (`tiktok-scraper7.p.rapidapi.com`), endpoint `/feed/search`
(pesquisa por palavra-chave/hashtag, testado e validado). Se usares outro
endpoint ou provider, ajusta `RAPIDAPI_HOST` / `RAPIDAPI_ENDPOINT` no `.env` e,
se o formato da resposta for diferente, a função `normalizar_item()` em
`coletor.py`.

## Uso

### 1. Coletar vídeos de um nicho

O `--nicho` é livre — usa o que quiseres, não fica preso a "barbearia":

```bash
python coletor.py --nicho fitness                    # TikTok (rede por omissão)
python coletor.py --nicho fitness --rede instagram    # o mesmo nicho, no Instagram
python coletor.py --nicho receitas --hashtag receitasfaceis --quantidade 30
python coletor.py --nicho pets --descarregar          # coleta + score + download dos candidatos
python coletor.py --nicho pets --mock                 # dados de exemplo, sem gastar API
python coletor.py --nicho pets --rede instagram --mock
```

Cada coleta guarda os vídeos no SQLite (`radar_viral.db`), ignora duplicados
(chave única por `id`, prefixado com a rede — `tiktok_...` / `instagram_...`)
e recalcula automaticamente o score viral. TikTok e Instagram do mesmo nicho
aparecem juntos no dashboard, com filtro por rede.

#### TikTok

Já validado e a funcionar (host `tiktok-scraper7.p.rapidapi.com`,
endpoint `/feed/search`) — não precisas de mexer em nada.

#### Instagram

Ainda não testado com uma chamada real (não tinha uma chave de Instagram para
validar). Passos:

1. No [RapidAPI Hub](https://rapidapi.com), subscreve uma API de Instagram
   com pesquisa por hashtag (ex.: "Instagram Scraper API2" ou "API de
   Estatísticas do Instagram").
2. Normalmente a **mesma `RAPIDAPI_KEY`** que já usas para o TikTok funciona —
   só muda o host. Atualiza no `.env`:
   ```
   RAPIDAPI_HOST_INSTAGRAM=<host que aparecer no painel de testes>
   RAPIDAPI_ENDPOINT_INSTAGRAM=<endpoint de pesquisa por hashtag>
   ```
3. Testa um pedido real (com `curl` ou no painel "Test Endpoint" do RapidAPI)
   e compara os nomes dos campos com os que `normalizar_item_instagram()` em
   `coletor.py` espera (`shortcode`, `caption`, `like_count`,
   `video_view_count`, `comment_count`, `owner.username`, `video_url`). Se
   forem diferentes, ajusta só essa função — foi exatamente este processo
   que corrigiu o TikTok.
4. Enquanto isso, `--mock` já funciona para o Instagram
   (`coletor/mock_videos_instagram.json`), para testares o dashboard.

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
- Filtro por nicho, **país**, rede e intervalo de datas.
- Botão **📋 Copiar legenda** (já com o crédito ao autor).
- Botão **⬇️ Baixar vídeo** (descarrega na hora, se ainda não tiver sido descarregado).
- Botão **✅ Marcar como usado** para não repetir sugestões (reversível).

### País

O TikTok devolve o país onde cada vídeo foi detetado (campo `region`, ex.: `BR`,
`PT`, `US`) e guardamos isso por vídeo. **Testámos ao vivo e confirmámos que a
API não filtra a pesquisa por país** — pedir `region=BR` devolve exatamente os
mesmos resultados que não pedir nada (parece ser ignorado no plano gratuito).
Por isso o filtro de país funciona **na dashboard**, sobre o que já foi
coletado, e não como parâmetro de coleta: quanto mais vídeos coletares (maior
`--quantidade`, mais coletas ao longo do tempo), mais variedade de países vais
ter para filtrar. Se um dia confirmares que a tua conta RapidAPI tem um plano
que suporta filtro por região na API, avisa que ligamos isso em `buscar_api_tiktok()`.

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
