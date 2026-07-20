"""Dashboard do Radar Viral.

Lista os candidatos por score, com preview, métricas e legenda sugerida
(sempre com crédito ao autor original). Correr com: python app.py
"""
from datetime import date, timedelta

from flask import Flask, abort, redirect, render_template, request, send_from_directory

import config
import db
from downloader import gerar_legenda

app = Flask(__name__)
db.init_db()


def _filtros():
    nicho = request.args.get("nicho", "").strip()
    rede = request.args.get("rede", "").strip()
    periodo = request.args.get("periodo", "semana")
    de = request.args.get("de", "")
    ate = request.args.get("ate", "")
    incluir_usados = request.args.get("usados") == "1"

    if not de and not ate:
        if periodo == "dia":
            de = date.today().isoformat()
        elif periodo == "semana":
            de = (date.today() - timedelta(days=7)).isoformat()
        # periodo == "tudo": sem limite de datas
    return nicho, rede, periodo, de, ate, incluir_usados


@app.route("/")
def index():
    nicho, rede, periodo, de, ate, incluir_usados = _filtros()

    sql = "SELECT * FROM videos WHERE candidato = 1"
    params: list = []
    if nicho:
        sql += " AND nicho = ?"
        params.append(nicho)
    if rede:
        sql += " AND rede = ?"
        params.append(rede)
    if de:
        sql += " AND date(data_coleta) >= date(?)"
        params.append(de)
    if ate:
        sql += " AND date(data_coleta) <= date(?)"
        params.append(ate)
    if not incluir_usados:
        sql += " AND usado = 0"
    sql += " ORDER BY score_viral DESC"

    with db.ligacao() as con:
        videos = con.execute(sql, params).fetchall()
        nichos = [r["nicho"] for r in con.execute(
            "SELECT DISTINCT nicho FROM videos ORDER BY nicho").fetchall()]

    cartoes = []
    for v in videos:
        v = dict(v)
        v["legenda"] = v["legenda_sugerida"] or gerar_legenda(
            v["username_autor"], v["descricao"])
        cartoes.append(v)

    return render_template(
        "index.html",
        videos=cartoes,
        nichos=nichos,
        nicho=nicho,
        rede=rede,
        periodo=periodo,
        de=de,
        ate=ate,
        incluir_usados=incluir_usados,
        threshold=config.SCORE_THRESHOLD,
    )


@app.route("/usado/<video_id>", methods=["POST"])
def marcar_usado(video_id):
    novo = 0 if request.form.get("desfazer") else 1
    with db.ligacao() as con:
        con.execute("UPDATE videos SET usado = ? WHERE id = ?", (novo, video_id))
    return redirect(request.form.get("voltar") or "/")


@app.route("/media/<nicho>/<video_id>.mp4")
def media(nicho, video_id):
    pasta = (config.DOWNLOADS_DIR / nicho).resolve()
    if not pasta.is_relative_to(config.DOWNLOADS_DIR.resolve()):
        abort(404)
    return send_from_directory(pasta, f"{video_id}.mp4")


if __name__ == "__main__":
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=False)
