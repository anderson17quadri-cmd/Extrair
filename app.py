"""Dashboard do Radar Viral.

Lista os candidatos por score, com preview, métricas e legenda sugerida
(sempre com crédito ao autor original). Correr com: python app.py
"""
from datetime import date, timedelta

import requests
from flask import Flask, abort, redirect, render_template, request, send_from_directory

import coletor
import config
import db
from downloader import baixar_video, gerar_legenda

app = Flask(__name__)
db.init_db()


def _filtros():
    nicho = request.args.get("nicho", "").strip()
    rede = request.args.get("rede", "").strip()
    pais = request.args.get("pais", "").strip().upper()
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
    return nicho, rede, pais, periodo, de, ate, incluir_usados


@app.route("/")
def index():
    nicho, rede, pais, periodo, de, ate, incluir_usados = _filtros()

    sql = "SELECT * FROM videos WHERE candidato = 1"
    params: list = []
    if nicho:
        sql += " AND nicho = ?"
        params.append(nicho)
    if rede:
        sql += " AND rede = ?"
        params.append(rede)
    if pais:
        sql += " AND pais = ?"
        params.append(pais)
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
        paises = [r["pais"] for r in con.execute(
            "SELECT DISTINCT pais FROM videos WHERE pais != '' ORDER BY pais").fetchall()]

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
        paises=paises,
        nicho=nicho,
        rede=rede,
        pais=pais,
        periodo=periodo,
        de=de,
        ate=ate,
        incluir_usados=incluir_usados,
        threshold=config.SCORE_THRESHOLD,
        erro=request.args.get("erro", ""),
    )


@app.route("/coletar", methods=["POST"])
def nova_coleta():
    """Dispara uma coleta real a partir da dashboard, sem precisar do terminal."""
    nicho = request.form.get("nicho", "").strip()
    hashtag = request.form.get("hashtag", "").strip() or nicho
    rede = request.form.get("rede", "tiktok").strip() or "tiktok"

    if not nicho:
        return redirect("/?erro=Escreve+um+nicho+antes+de+coletar")
    if not config.RAPIDAPI_KEY:
        return redirect("/?erro=Falta+a+RAPIDAPI_KEY+no+.env+do+servidor")

    try:
        coletor.coletar(nicho, hashtag, quantidade=20, rede=rede, mock=False)
    except requests.RequestException as erro:
        return redirect(f"/?nicho={nicho}&rede={rede}&periodo=tudo&erro=Erro+na+API%3A+{erro}")
    except Exception as erro:
        return redirect(f"/?nicho={nicho}&rede={rede}&periodo=tudo&erro={erro}")

    return redirect(f"/?nicho={nicho}&rede={rede}&periodo=tudo")


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
    forcar_download = request.args.get("download") == "1"
    return send_from_directory(pasta, f"{video_id}.mp4", as_attachment=forcar_download)


@app.route("/baixar/<video_id>", methods=["POST"])
def baixar(video_id):
    """Descarrega o vídeo do candidato na hora, a pedido do dashboard (via fetch/JS)."""
    with db.ligacao() as con:
        video = con.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
    if video is None:
        abort(404)

    if not video["ficheiro_local"]:
        legenda = gerar_legenda(video["username_autor"], video["descricao"])
        try:
            caminho = baixar_video(video)
        except requests.RequestException as erro:
            print(f"[dashboard] erro ao baixar {video_id}: {erro}")
            return {"ok": False, "erro": str(erro)}, 502
        if not caminho:
            return {"ok": False, "erro": "vídeo sem url de download"}, 502
        with db.ligacao() as con:
            con.execute(
                "UPDATE videos SET ficheiro_local = ?, legenda_sugerida = ? WHERE id = ?",
                (caminho, legenda, video_id),
            )

    return {"ok": True}


if __name__ == "__main__":
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=False)
