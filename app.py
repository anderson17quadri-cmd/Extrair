"""Dashboard do Radar Viral.

Lista os candidatos por score, com preview, métricas e legenda sugerida
(sempre com crédito ao autor original). Correr com: python app.py
"""
import io
import json
import zipfile
from datetime import date, timedelta

import requests
from flask import Flask, abort, redirect, render_template, request, send_file, send_from_directory

import coletor
import config
import db
import perfil
import uso_api
from downloader import baixar_video, gerar_legenda

app = Flask(__name__)
db.init_db()


# países mostrados por omissão até o utilizador escolher outros no filtro
PAISES_PADRAO = ["PT", "BR"]


def _filtros():
    nicho = request.args.get("nicho", "").strip()
    rede = request.args.get("rede", "").strip()
    if "pais_definido" in request.args:
        # o filtro já foi submetido pelo menos uma vez — respeita a escolha,
        # mesmo que tenha ficado sem nenhuma marcada (= "todos os países")
        pais = [p.upper() for p in request.args.getlist("pais") if p]
    else:
        pais = list(PAISES_PADRAO)
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


@app.route("/radar-viral")
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
        marcadores = ",".join("?" * len(pais))
        sql += f" AND pais IN ({marcadores})"
        params.extend(pais)
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
        paises_com_dados = [r["pais"] for r in con.execute(
            "SELECT DISTINCT pais FROM videos WHERE pais != '' ORDER BY pais").fetchall()]
        # PT/BR aparecem sempre como opção, mesmo antes de haver dados coletados
        paises = sorted(set(paises_com_dados) | set(PAISES_PADRAO))

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
        uso=uso_api.resumo(),
    )


@app.route("/coletar", methods=["POST"])
def nova_coleta():
    """Dispara uma coleta real a partir da dashboard, sem precisar do terminal."""
    nicho = request.form.get("nicho", "").strip()
    hashtag = request.form.get("hashtag", "").strip() or nicho
    rede = request.form.get("rede", "tiktok").strip() or "tiktok"

    if not nicho:
        return redirect("/radar-viral?erro=Escreve+um+nicho+antes+de+coletar")
    if not config.RAPIDAPI_KEY:
        return redirect("/radar-viral?erro=Falta+a+RAPIDAPI_KEY+no+.env+do+servidor")

    try:
        coletor.coletar(nicho, hashtag, quantidade=20, rede=rede, mock=False)
    except requests.RequestException as erro:
        return redirect(f"/radar-viral?nicho={nicho}&rede={rede}&periodo=tudo&erro=Erro+na+API%3A+{erro}")
    except Exception as erro:
        return redirect(f"/radar-viral?nicho={nicho}&rede={rede}&periodo=tudo&erro={erro}")

    return redirect(f"/radar-viral?nicho={nicho}&rede={rede}&periodo=tudo")


@app.route("/usado/<video_id>", methods=["POST"])
def marcar_usado(video_id):
    novo = 0 if request.form.get("desfazer") else 1
    with db.ligacao() as con:
        con.execute("UPDATE videos SET usado = ? WHERE id = ?", (novo, video_id))
    return redirect(request.form.get("voltar") or "/radar-viral")


def _pasta_perfil(username: str):
    pasta = (config.DOWNLOADS_DIR / "perfis" / username).resolve()
    base = (config.DOWNLOADS_DIR / "perfis").resolve()
    if not pasta.is_relative_to(base):
        abort(404)
    return pasta


def _galeria_perfil(username: str) -> list[dict]:
    ficheiro_legendas = _pasta_perfil(username) / "legendas.json"
    if not ficheiro_legendas.exists():
        return []
    legendas = json.loads(ficheiro_legendas.read_text(encoding="utf-8"))
    pasta = _pasta_perfil(username)
    itens = [
        {"arquivo": nome, **info}
        for nome, info in legendas.items()
        if (pasta / nome).exists()
    ]
    itens.sort(key=lambda i: i["arquivo"], reverse=True)
    return itens


@app.route("/")
def perfil_pagina():
    username = request.args.get("username", "").strip()
    with_perfis = config.DOWNLOADS_DIR / "perfis"
    perfis_existentes = sorted(p.name for p in with_perfis.iterdir() if p.is_dir()) if with_perfis.exists() else []
    return render_template(
        "perfil.html",
        username=username,
        galeria=_galeria_perfil(username) if username else [],
        perfis_existentes=perfis_existentes,
        erro=request.args.get("erro", ""),
        aviso=request.args.get("aviso", ""),
        uso=uso_api.resumo(),
    )


@app.route("/perfil/baixar", methods=["POST"])
def perfil_baixar():
    """Dispara o download de um perfil inteiro a partir da dashboard.

    Se o perfil já tiver conteúdo baixado, não gasta cota da API de novo a
    não ser que o pedido venha com forcar=1 (botão "Buscar posts novos").
    """
    entrada = request.form.get("perfil", "").strip()
    forcar = request.form.get("forcar") == "1"
    try:
        quantidade = min(max(int(request.form.get("quantidade") or 30), 1), 100)
    except ValueError:
        quantidade = 30

    if not entrada:
        return redirect("/?erro=Cola+o+link+ou+username+do+perfil")

    try:
        username = perfil.extrair_username(entrada)
    except ValueError as erro:
        return redirect(f"/?erro={erro}")

    if not forcar and _galeria_perfil(username):
        return redirect(f"/?username={username}&aviso=ja_existe")

    if not config.RAPIDAPI_KEY:
        return redirect("/?erro=Falta+a+RAPIDAPI_KEY+no+.env+do+servidor")

    try:
        perfil.baixar_perfil(username, quantidade, mock=False)
    except (RuntimeError, requests.RequestException) as erro:
        return redirect(f"/?erro=Erro+na+API%3A+{erro}")

    return redirect(f"/?username={username}")


@app.route("/perfil/midia/<username>/<path:arquivo>")
def perfil_midia(username, arquivo):
    pasta = _pasta_perfil(username)
    forcar_download = request.args.get("download") == "1"
    return send_from_directory(pasta, arquivo, as_attachment=forcar_download)


@app.route("/perfil/zip", methods=["POST"])
def perfil_zip():
    """Zipa só os ficheiros selecionados na galeria, para levar para a landing page."""
    username = request.form.get("username", "").strip()
    arquivos = request.form.getlist("arquivo")
    if not username or not arquivos:
        return redirect(f"/?username={username}&erro=Seleciona+pelo+menos+um+ficheiro")

    pasta = _pasta_perfil(username)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_ficheiro:
        for nome in arquivos:
            caminho = (pasta / nome).resolve()
            if caminho.is_relative_to(pasta) and caminho.exists():
                zip_ficheiro.write(caminho, arcname=nome)
    buffer.seek(0)
    return send_file(buffer, mimetype="application/zip", as_attachment=True,
                      download_name=f"{username}-selecionados.zip")


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
