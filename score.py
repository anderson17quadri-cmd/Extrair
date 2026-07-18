"""Cálculo do score viral.

score_viral = (views / horas desde publicação) * (1 + PESO_ENGAGEMENT * engagement)
engagement  = (likes + comentários + partilhas) / views

Vídeos com score >= SCORE_THRESHOLD ficam marcados como "candidato".
"""
from datetime import datetime, timezone

import config
import db


def calcular_score(video) -> float:
    views = video["views"] or 0
    if views <= 0:
        return 0.0

    horas = 1.0
    if video["data_publicacao"]:
        try:
            publicado = datetime.fromisoformat(video["data_publicacao"])
            if publicado.tzinfo is None:
                publicado = publicado.replace(tzinfo=timezone.utc)
            horas = max(
                (datetime.now(timezone.utc) - publicado).total_seconds() / 3600, 1.0
            )
        except ValueError:
            pass

    velocidade = views / horas
    engagement = (
        (video["likes"] or 0) + (video["comentarios"] or 0) + (video["partilhas"] or 0)
    ) / views
    return round(velocidade * (1 + config.PESO_ENGAGEMENT * engagement), 2)


def atualizar_scores(nicho: str | None = None) -> int:
    """Recalcula scores e marca candidatos. Devolve o nº de candidatos."""
    db.init_db()
    with db.ligacao() as con:
        if nicho:
            linhas = con.execute("SELECT * FROM videos WHERE nicho = ?", (nicho,)).fetchall()
        else:
            linhas = con.execute("SELECT * FROM videos").fetchall()

        candidatos = 0
        for video in linhas:
            valor = calcular_score(video)
            e_candidato = 1 if valor >= config.SCORE_THRESHOLD else 0
            candidatos += e_candidato
            con.execute(
                "UPDATE videos SET score_viral = ?, candidato = ? WHERE id = ?",
                (valor, e_candidato, video["id"]),
            )
    return candidatos


def listar_candidatos(nicho: str | None = None):
    """Candidatos ordenados por score decrescente."""
    with db.ligacao() as con:
        sql = "SELECT * FROM videos WHERE candidato = 1"
        params: list = []
        if nicho:
            sql += " AND nicho = ?"
            params.append(nicho)
        sql += " ORDER BY score_viral DESC"
        return con.execute(sql, params).fetchall()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Recalcula scores virais")
    parser.add_argument("--nicho", help="Limitar a um nicho")
    args = parser.parse_args()
    total = atualizar_scores(args.nicho)
    print(f"{total} candidato(s) com score >= {config.SCORE_THRESHOLD}.")
    for v in listar_candidatos(args.nicho):
        print(f"  {v['score_viral']:>10.1f}  @{v['username_autor']}  {v['descricao'][:60]}")
