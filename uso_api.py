"""Contador de chamadas reais feitas às APIs da RapidAPI.

Não é o limite oficial da tua conta (esse só o dashboard da RapidAPI sabe) —
é só um registo local pra dares por conta de quanto já gastaste hoje/mês e
evitares surpresas. Cada chamada aqui contada = 1 requisição HTTP real à
RapidAPI (TikTok search, Instagram search ou Instagram posts).
"""
import json
from datetime import date, datetime, timezone

import config

FICHEIRO = config.BASE_DIR / "uso_api.json"


def _ler() -> list[dict]:
    if not FICHEIRO.exists():
        return []
    try:
        return json.loads(FICHEIRO.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def registar_chamada(origem: str) -> None:
    chamadas = _ler()
    chamadas.append({"quando": datetime.now(timezone.utc).isoformat(), "origem": origem})
    FICHEIRO.write_text(json.dumps(chamadas), encoding="utf-8")


def resumo() -> dict:
    chamadas = _ler()
    hoje = date.today().isoformat()
    mes = hoje[:7]
    return {
        "hoje": sum(1 for c in chamadas if c["quando"].startswith(hoje)),
        "mes": sum(1 for c in chamadas if c["quando"].startswith(mes)),
        "total": len(chamadas),
    }
