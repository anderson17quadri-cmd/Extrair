"""Download dos vídeos candidatos.

- Só descarrega vídeos marcados como candidato (poupa espaço e banda).
- Guarda em downloads/{nicho}/{id}.mp4.
- O ficheiro é gravado tal como vem da API (versão COM marca de água) —
  nunca é processado, cortado ou editado.
- Gera a legenda sugerida com crédito ao autor original.
"""
import argparse

import requests

import config
import db

TAMANHO_DESCRICAO_CURTA = 80


def gerar_legenda(username_autor: str, descricao: str) -> str:
    curta = (descricao or "").strip()
    if len(curta) > TAMANHO_DESCRICAO_CURTA:
        curta = curta[:TAMANHO_DESCRICAO_CURTA].rstrip() + "…"
    legenda = f"🔥 via @{username_autor}"
    if curta:
        legenda += f" · {curta}"
    return legenda


def baixar_video(video) -> str | None:
    """Descarrega um vídeo (sem qualquer processamento) e devolve o caminho local."""
    if not video["url_download"]:
        print(f"  [skip] {video['id']}: sem url_download")
        return None

    pasta = config.DOWNLOADS_DIR / video["nicho"]
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"{video['id']}.mp4"
    if destino.exists() and destino.stat().st_size > 0:
        return str(destino)

    with requests.get(video["url_download"], stream=True, timeout=60) as resposta:
        resposta.raise_for_status()
        with open(destino, "wb") as f:
            for pedaco in resposta.iter_content(chunk_size=1024 * 256):
                f.write(pedaco)
    return str(destino)


def baixar_candidatos(nicho: str | None = None) -> int:
    """Descarrega todos os candidatos ainda sem ficheiro local."""
    db.init_db()
    with db.ligacao() as con:
        sql = ("SELECT * FROM videos WHERE candidato = 1 "
               "AND (ficheiro_local IS NULL OR ficheiro_local = '')")
        params: list = []
        if nicho:
            sql += " AND nicho = ?"
            params.append(nicho)
        pendentes = con.execute(sql + " ORDER BY score_viral DESC", params).fetchall()

    descarregados = 0
    for video in pendentes:
        legenda = gerar_legenda(video["username_autor"], video["descricao"])
        try:
            caminho = baixar_video(video)
        except requests.RequestException as erro:
            print(f"  [erro] {video['id']}: {erro}")
            caminho = None
        with db.ligacao() as con:
            con.execute(
                "UPDATE videos SET ficheiro_local = ?, legenda_sugerida = ? WHERE id = ?",
                (caminho, legenda, video["id"]),
            )
        if caminho:
            descarregados += 1
            print(f"  [ok] {video['id']} -> {caminho}")
    print(f"{descarregados}/{len(pendentes)} candidato(s) descarregado(s).")
    return descarregados


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Descarrega vídeos candidatos")
    parser.add_argument("--nicho", help="Limitar a um nicho")
    args = parser.parse_args()
    baixar_candidatos(args.nicho)
