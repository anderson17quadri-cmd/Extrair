"""Coletor de vídeos em alta no TikTok e Instagram via RapidAPI.

Uso:
    python coletor.py --nicho barbearia                          # TikTok (omissão)
    python coletor.py --nicho barbearia --rede instagram
    python coletor.py --nicho barbearia --hashtag barbeiro --quantidade 30
    python coletor.py --nicho barbearia --descarregar             # coleta + score + download
    python coletor.py --nicho barbearia --agendar 60               # repete a cada 60 min
    python coletor.py --nicho barbearia --mock                     # dados de exemplo, sem API

O --nicho é livre — usa o que quiseres (ex.: "fitness", "receitas", "pets").
Após cada coleta o score viral é recalculado automaticamente.
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

import config
import db
import score


def _extrair_hashtags(texto: str) -> str:
    return " ".join(re.findall(r"#\w+", texto or ""))


# --------------------------------------------------------------------------
# TikTok — validado com chamadas reais à tiktok-scraper7 (RapidAPI)
# --------------------------------------------------------------------------

def normalizar_item_tiktok(item: dict, nicho: str) -> dict:
    """Converte um item da API tiktok-scraper7 no formato da nossa tabela.

    IMPORTANTE: usamos `wmplay` (vídeo COM marca de água) como url_download,
    para preservar a autoria original.
    """
    autor = item.get("author") or {}
    descricao = item.get("title") or ""
    criado = item.get("create_time") or 0
    data_pub = (
        datetime.fromtimestamp(int(criado), tz=timezone.utc).isoformat()
        if criado
        else None
    )
    video_id = str(item.get("video_id") or item.get("aweme_id") or "")
    return {
        "id": f"tiktok_{video_id}" if video_id else "",
        "rede": "tiktok",
        "nicho": nicho,
        "autor": autor.get("nickname") or "",
        "username_autor": autor.get("unique_id") or "",
        "descricao": descricao,
        "hashtags": _extrair_hashtags(descricao),
        "views": int(item.get("play_count") or 0),
        "likes": int(item.get("digg_count") or 0),
        "comentarios": int(item.get("comment_count") or 0),
        "partilhas": int(item.get("share_count") or 0),
        "data_publicacao": data_pub,
        "url_video": item.get("share_url")
        or f"https://www.tiktok.com/@{autor.get('unique_id', '')}/video/{video_id}",
        # wmplay = versão com watermark; nunca usar a versão "play" sem marca
        "url_download": item.get("wmplay") or item.get("download_url") or "",
        "data_coleta": datetime.now(timezone.utc).isoformat(),
    }


def buscar_api_tiktok(hashtag: str, quantidade: int) -> list[dict]:
    """Pesquisa vídeos por palavra-chave/hashtag via /feed/search (RapidAPI)."""
    url = f"https://{config.RAPIDAPI_HOST}{config.RAPIDAPI_ENDPOINT}"
    resposta = requests.get(
        url,
        headers={
            "x-rapidapi-key": config.RAPIDAPI_KEY,
            "x-rapidapi-host": config.RAPIDAPI_HOST,
        },
        params={"keywords": hashtag, "count": quantidade, "cursor": 0},
        timeout=30,
    )
    resposta.raise_for_status()
    corpo = resposta.json()
    # tiktok-scraper7 devolve {"data": {"videos": [...]}}
    dados = corpo.get("data") or {}
    videos = dados.get("videos") or dados.get("aweme_list") or []
    if not videos:
        print(f"Aviso: resposta sem vídeos: {json.dumps(corpo)[:300]}")
    return videos


# --------------------------------------------------------------------------
# Instagram — AINDA POR VALIDAR: os nomes de campos abaixo são os mais comuns
# entre APIs de Instagram no RapidAPI, mas cada provider varia. Assim que
# subscreveres uma (ex.: "instagram-scraper-api2" ou "API de Estatísticas do
# Instagram"), testa um pedido real e ajusta esta função aos campos que
# vierem de facto — foi exatamente este processo que corrigiu o TikTok.
# --------------------------------------------------------------------------

def normalizar_item_instagram(item: dict, nicho: str) -> dict:
    """Converte um item de uma API de hashtag do Instagram no formato da tabela.

    Instagram não expõe contagem de partilhas publicamente — fica sempre 0.
    IMPORTANTE: gravamos o vídeo tal como a API o devolve, sem qualquer
    edição — a marca/autoria do Instagram não é removida nem sobreposta.
    """
    autor = item.get("owner") or item.get("user") or {}
    descricao = item.get("caption") or ""
    if not descricao:
        edges = (item.get("edge_media_to_caption") or {}).get("edges") or []
        if edges:
            descricao = edges[0].get("node", {}).get("text", "")
    criado = item.get("taken_at_timestamp") or item.get("taken_at") or 0
    data_pub = (
        datetime.fromtimestamp(int(criado), tz=timezone.utc).isoformat()
        if criado
        else None
    )
    shortcode = str(item.get("shortcode") or item.get("code") or item.get("id") or "")
    return {
        "id": f"instagram_{shortcode}" if shortcode else "",
        "rede": "instagram",
        "nicho": nicho,
        "autor": autor.get("full_name") or "",
        "username_autor": autor.get("username") or "",
        "descricao": descricao or "",
        "hashtags": _extrair_hashtags(descricao),
        "views": int(item.get("video_view_count") or item.get("play_count") or 0),
        "likes": int(item.get("like_count") or item.get("edge_liked_by", {}).get("count", 0) or 0),
        "comentarios": int(item.get("comment_count") or item.get("edge_media_to_comment", {}).get("count", 0) or 0),
        "partilhas": 0,
        "data_publicacao": data_pub,
        "url_video": f"https://www.instagram.com/reel/{shortcode}/" if shortcode else "",
        "url_download": item.get("video_url") or item.get("video_download_url") or "",
        "data_coleta": datetime.now(timezone.utc).isoformat(),
    }


def buscar_api_instagram(hashtag: str, quantidade: int) -> list[dict]:
    """Pesquisa reels por hashtag via RapidAPI (endpoint configurável no .env)."""
    hashtag = hashtag.lstrip("#")
    url = f"https://{config.RAPIDAPI_HOST_INSTAGRAM}{config.RAPIDAPI_ENDPOINT_INSTAGRAM}"
    resposta = requests.get(
        url,
        headers={
            "x-rapidapi-key": config.RAPIDAPI_KEY,
            "x-rapidapi-host": config.RAPIDAPI_HOST_INSTAGRAM,
        },
        params={"hashtag": hashtag, "count": quantidade},
        timeout=30,
    )
    resposta.raise_for_status()
    corpo = resposta.json()
    dados = corpo.get("data") or corpo
    itens = (
        dados.get("items")
        or dados.get("medias")
        or dados.get("edges")
        or dados.get("posts")
        or []
    )
    if not itens:
        print(f"Aviso: resposta sem posts: {json.dumps(corpo)[:300]}")
    return itens


REDES = {
    "tiktok": (buscar_api_tiktok, normalizar_item_tiktok),
    "instagram": (buscar_api_instagram, normalizar_item_instagram),
}


def buscar_mock(rede: str) -> list[dict]:
    nome_ficheiro = "mock_videos.json" if rede == "tiktok" else "mock_videos_instagram.json"
    ficheiro = Path(__file__).parent / "coletor" / nome_ficheiro
    itens = json.loads(ficheiro.read_text(encoding="utf-8"))
    agora = datetime.now(timezone.utc).timestamp()
    campo_tempo = "create_time" if rede == "tiktok" else "taken_at_timestamp"
    # _horas_atras torna os dados de exemplo sempre "recentes" para o score
    for item in itens:
        item.setdefault(campo_tempo, int(agora - item.pop("_horas_atras", 24) * 3600))
    return itens


def coletar(nicho: str, hashtag: str, quantidade: int, rede: str = "tiktok", mock: bool = False) -> int:
    if rede not in REDES:
        sys.exit(f"ERRO: --rede deve ser uma de: {', '.join(REDES)}")
    if not mock and not config.RAPIDAPI_KEY:
        sys.exit(
            "ERRO: RAPIDAPI_KEY não definida. Copia .env.example para .env "
            "e coloca lá a tua chave (nunca no código)."
        )

    db.init_db()
    buscar_api, normalizar_item = REDES[rede]
    itens = buscar_mock(rede) if mock else buscar_api(hashtag, quantidade)
    novos = 0
    for item in itens:
        video = normalizar_item(item, nicho)
        if not video["id"]:
            continue
        if db.inserir_video(video):
            novos += 1
    print(f"[{rede}/{nicho}] {len(itens)} vídeos recebidos, {novos} novos guardados.")
    candidatos = score.atualizar_scores(nicho)
    print(f"[{nicho}] scores atualizados — {candidatos} candidato(s) acima do threshold.")
    return novos


def main():
    parser = argparse.ArgumentParser(description="Coletor do Radar Viral")
    parser.add_argument("--nicho", required=True, help="Nicho a pesquisar (livre, ex.: fitness, receitas, pets)")
    parser.add_argument("--rede", choices=sorted(REDES), default="tiktok", help="Rede social a coletar")
    parser.add_argument("--hashtag", help="Palavra-chave/hashtag a usar na API (por omissão = nicho)")
    parser.add_argument("--quantidade", type=int, default=30, help="Nº de vídeos a pedir")
    parser.add_argument("--descarregar", action="store_true",
                        help="Descarrega os candidatos logo após a coleta")
    parser.add_argument("--agendar", type=int, metavar="MINUTOS",
                        help="Repete a coleta a cada N minutos (alternativa ao cron)")
    parser.add_argument("--mock", action="store_true",
                        help="Usa dados de exemplo em vez da API (para testes)")
    args = parser.parse_args()

    hashtag = args.hashtag or args.nicho

    while True:
        coletar(args.nicho, hashtag, args.quantidade, rede=args.rede, mock=args.mock)
        if args.descarregar:
            import downloader
            downloader.baixar_candidatos(args.nicho)
        if not args.agendar:
            break
        print(f"Próxima coleta em {args.agendar} min...")
        time.sleep(args.agendar * 60)


if __name__ == "__main__":
    main()
