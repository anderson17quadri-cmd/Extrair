"""Baixa TODAS as fotos e vídeos de um perfil público do Instagram.

Uso:
    python perfil.py --perfil https://instagram.com/nomedaempresa
    python perfil.py --perfil nomedaempresa --quantidade 100
    python perfil.py --perfil nomedaempresa --mock          # testa sem gastar API
    python perfil.py --perfil nomedaempresa --debug          # mostra o 1º post cru

Pensado para montar landing pages com o próprio conteúdo do cliente (fotos e
vídeos que ele já publicou), não para reusar conteúdo de terceiros.

IMPORTANTE — endpoint ainda não validado com uma chamada real (ao contrário
do resto do coletor): a API "Instagram Social" tem um endpoint de posts por
utilizador, mas o nome exato dos campos (paginação, urls das fotos/vídeos no
carrossel) pode variar. Corre primeiro com --mock, depois com --debug e
--quantidade 3 para conferir a resposta real e ajustar `extrair_midias()` e
`buscar_posts_perfil()` se precisar — é o mesmo processo que já foi feito
para validar o coletor de TikTok e a busca do Instagram (ver README).

Este script é independente do fluxo de "Radar Viral" (score/candidato/
dashboard) — aqui o objetivo é levar tudo o que o perfil publicou, não achar
o que está a viralizar.
"""
import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests

import config

CURSORES_POSSIVEIS = ["pagination_token", "next_cursor", "end_cursor", "next_page_id"]
MAX_PAGINAS = 20


def extrair_username(entrada: str) -> str:
    """Aceita um link (https://instagram.com/fulano/) ou já o @username."""
    entrada = entrada.strip()
    if "instagram.com" in entrada:
        caminho = urlparse(entrada if "://" in entrada else f"https://{entrada}").path
        partes = [p for p in caminho.split("/") if p]
        if not partes:
            sys.exit(f"ERRO: não consegui extrair o username de '{entrada}'")
        return partes[0]
    return entrada.lstrip("@")


def _primeira_lista(corpo: dict) -> list:
    for chave in ("body", "items", "posts", "data"):
        valor = corpo.get(chave)
        if isinstance(valor, list):
            return valor
        if isinstance(valor, dict):
            for subchave in ("items", "posts"):
                if isinstance(valor.get(subchave), list):
                    return valor[subchave]
    return []


def buscar_posts_perfil(username: str, quantidade: int, debug: bool = False) -> list[dict]:
    """Percorre as páginas do endpoint de posts até juntar `quantidade` itens."""
    url = f"https://{config.RAPIDAPI_HOST_INSTAGRAM}{config.RAPIDAPI_ENDPOINT_INSTAGRAM_POSTS}"
    itens: list[dict] = []
    parametros_extra: dict = {}
    for pagina in range(MAX_PAGINAS):
        resposta = requests.get(
            url,
            headers={
                "x-rapidapi-key": config.RAPIDAPI_KEY,
                "x-rapidapi-host": config.RAPIDAPI_HOST_INSTAGRAM,
                "Accept": "application/json",
            },
            params={"username": username, **parametros_extra},
            timeout=30,
        )
        resposta.raise_for_status()
        corpo = resposta.json()
        if debug and pagina == 0:
            print("--- [debug] resposta crua da 1ª página ---")
            print(json.dumps(corpo, indent=2, ensure_ascii=False)[:4000])
            print("--- [debug] fim ---")

        pagina_itens = _primeira_lista(corpo)
        if not pagina_itens:
            break
        itens.extend(pagina_itens)
        if len(itens) >= quantidade:
            break

        # confirmado numa chamada real (endpoint de comentários, mesma família
        # de API): o cursor vem em corpo["meta"]["pagination_token"]
        meta = corpo.get("meta") or {}
        cursor = meta.get("pagination_token") or next(
            (corpo[c] for c in CURSORES_POSSIVEIS if corpo.get(c)),
            None,
        )
        if not cursor:
            break
        parametros_extra = {"pagination_token": cursor}

    if not itens:
        print(f"Aviso: nenhum post encontrado para '{username}'. Usa --debug para ver a resposta crua.")
    return itens[:quantidade]


def extrair_midias(item: dict) -> list[dict]:
    """Devolve uma lista de {url, tipo} — um item por foto/vídeo do post.

    media_type: 1 = foto, 2 = vídeo, 8 = carrossel (várias fotos/vídeos).
    """
    tipo = item.get("media_type")
    if tipo == 8:
        midias = []
        for sub in item.get("carousel_media") or item.get("resources") or []:
            url = sub.get("media_url") or sub.get("video_url") or sub.get("display_url")
            if url:
                midias.append({"url": url, "tipo": "video" if sub.get("media_type") == 2 else "foto"})
        return midias
    url = item.get("media_url") or item.get("video_url") or item.get("display_url")
    if not url:
        return []
    return [{"url": url, "tipo": "video" if tipo == 2 else "foto"}]


def gerar_legenda(username: str, descricao: str) -> str:
    curta = (descricao or "").strip()
    return f"via @{username}" + (f" · {curta}" if curta else "")


def baixar_ficheiro(url: str, destino: Path) -> None:
    if destino.exists() and destino.stat().st_size > 0:
        return
    with requests.get(url, stream=True, timeout=60) as resposta:
        resposta.raise_for_status()
        with open(destino, "wb") as f:
            for pedaco in resposta.iter_content(chunk_size=1024 * 256):
                f.write(pedaco)


def baixar_perfil(username: str, quantidade: int, mock: bool = False, debug: bool = False) -> int:
    if not mock and not config.RAPIDAPI_KEY:
        sys.exit(
            "ERRO: RAPIDAPI_KEY não definida. Copia .env.example para .env "
            "e coloca lá a tua chave (nunca no código)."
        )

    if mock:
        ficheiro = Path(__file__).parent / "coletor" / "mock_perfil_instagram.json"
        posts = json.loads(ficheiro.read_text(encoding="utf-8"))
    else:
        posts = buscar_posts_perfil(username, quantidade, debug=debug)

    pasta = config.DOWNLOADS_DIR / "perfis" / username
    pasta.mkdir(parents=True, exist_ok=True)
    ficheiro_legendas = pasta / "legendas.json"
    legendas = json.loads(ficheiro_legendas.read_text(encoding="utf-8")) if ficheiro_legendas.exists() else {}

    baixados = 0
    for post in posts:
        shortcode = str(post.get("shortcode") or post.get("id") or "")
        if not shortcode:
            continue
        autor = (post.get("user") or {}).get("username") or username
        legenda = gerar_legenda(autor, post.get("caption") or "")
        permalink = post.get("permalink") or f"https://www.instagram.com/p/{shortcode}/"

        midias = extrair_midias(post)
        for indice, midia in enumerate(midias):
            extensao = "mp4" if midia["tipo"] == "video" else "jpg"
            sufixo = f"_{indice + 1}" if len(midias) > 1 else ""
            nome_ficheiro = f"{shortcode}{sufixo}.{extensao}"
            destino = pasta / nome_ficheiro
            try:
                baixar_ficheiro(midia["url"], destino)
            except requests.RequestException as erro:
                print(f"  [erro] {nome_ficheiro}: {erro}")
                continue
            legendas[nome_ficheiro] = {
                "legenda": legenda,
                "url_post": permalink,
                "tipo": midia["tipo"],
            }
            baixados += 1
            print(f"  [ok] {nome_ficheiro}")

    ficheiro_legendas.write_text(json.dumps(legendas, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[{username}] {baixados} ficheiro(s) em {pasta}")
    return baixados


def main():
    parser = argparse.ArgumentParser(description="Baixa todas as fotos/vídeos de um perfil do Instagram")
    parser.add_argument("--perfil", required=True, help="Link ou @username do perfil")
    parser.add_argument("--quantidade", type=int, default=200, help="Máx. de posts a percorrer")
    parser.add_argument("--mock", action="store_true", help="Usa dados de exemplo em vez da API")
    parser.add_argument("--debug", action="store_true", help="Mostra a resposta crua da 1ª página da API")
    args = parser.parse_args()

    username = extrair_username(args.perfil)
    baixar_perfil(username, args.quantidade, mock=args.mock, debug=args.debug)


if __name__ == "__main__":
    main()
