"""Coletor de vídeos em alta no TikTok via RapidAPI.

Uso:
    python coletor.py --nicho barbearia
    python coletor.py --nicho barbearia --hashtag barbeiro --quantidade 30
    python coletor.py --nicho barbearia --descarregar      # coleta + score + download
    python coletor.py --nicho barbearia --agendar 60       # repete a cada 60 min
    python coletor.py --nicho barbearia --mock             # dados de exemplo, sem API

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


def normalizar_item(item: dict, nicho: str) -> dict:
    """Converte um item da API tiktok-scraper7 no formato da nossa tabela.

    Se usares outro endpoint do RapidAPI, ajusta apenas esta função.
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
    return {
        "id": str(item.get("video_id") or item.get("aweme_id") or ""),
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
        or f"https://www.tiktok.com/@{autor.get('unique_id', '')}/video/{item.get('video_id', '')}",
        # wmplay = versão com watermark; nunca usar a versão "play" sem marca
        "url_download": item.get("wmplay") or item.get("download_url") or "",
        "data_coleta": datetime.now(timezone.utc).isoformat(),
    }


def buscar_api(hashtag: str, quantidade: int) -> list[dict]:
    """Chama o endpoint de hashtag/challenge do RapidAPI."""
    if not config.RAPIDAPI_KEY:
        sys.exit(
            "ERRO: RAPIDAPI_KEY não definida. Copia .env.example para .env "
            "e coloca lá a tua chave (nunca no código)."
        )
    url = f"https://{config.RAPIDAPI_HOST}{config.RAPIDAPI_ENDPOINT}"
    resposta = requests.get(
        url,
        headers={
            "x-rapidapi-key": config.RAPIDAPI_KEY,
            "x-rapidapi-host": config.RAPIDAPI_HOST,
        },
        params={"challenge_name": hashtag, "count": quantidade},
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


def buscar_mock() -> list[dict]:
    ficheiro = Path(__file__).parent / "coletor" / "mock_videos.json"
    itens = json.loads(ficheiro.read_text(encoding="utf-8"))
    agora = datetime.now(timezone.utc).timestamp()
    # _horas_atras torna os dados de exemplo sempre "recentes" para o score
    for item in itens:
        item.setdefault("create_time", int(agora - item.pop("_horas_atras", 24) * 3600))
    return itens


def coletar(nicho: str, hashtag: str, quantidade: int, mock: bool = False) -> int:
    db.init_db()
    itens = buscar_mock() if mock else buscar_api(hashtag, quantidade)
    novos = 0
    for item in itens:
        video = normalizar_item(item, nicho)
        if not video["id"]:
            continue
        if db.inserir_video(video):
            novos += 1
    print(f"[{nicho}] {len(itens)} vídeos recebidos, {novos} novos guardados.")
    candidatos = score.atualizar_scores(nicho)
    print(f"[{nicho}] scores atualizados — {candidatos} candidato(s) acima do threshold.")
    return novos


def main():
    parser = argparse.ArgumentParser(description="Coletor do Radar Viral")
    parser.add_argument("--nicho", required=True, help="Nicho a pesquisar (ex.: barbearia)")
    parser.add_argument("--hashtag", help="Hashtag a usar na API (por omissão = nicho)")
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
        coletar(args.nicho, hashtag, args.quantidade, mock=args.mock)
        if args.descarregar:
            import downloader
            downloader.baixar_candidatos(args.nicho)
        if not args.agendar:
            break
        print(f"Próxima coleta em {args.agendar} min...")
        time.sleep(args.agendar * 60)


if __name__ == "__main__":
    main()
