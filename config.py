"""Configuração central do Radar Viral.

Lê tudo do ficheiro .env (nunca hardcodar chaves aqui).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# --- RapidAPI -----------------------------------------------------------
# A chave vem SEMPRE do .env — ver .env.example
# A mesma RAPIDAPI_KEY costuma servir para qualquer API que subscrevas na tua
# conta RapidAPI — só o host/endpoint muda consoante a rede social.
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")

# TikTok (por omissão: tiktok-scraper7 — validado e a funcionar)
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST", "tiktok-scraper7.p.rapidapi.com")
RAPIDAPI_ENDPOINT = os.getenv("RAPIDAPI_ENDPOINT", "/feed/search")

# Instagram (ajusta ao endpoint que subscreveres — ver README)
RAPIDAPI_HOST_INSTAGRAM = os.getenv(
    "RAPIDAPI_HOST_INSTAGRAM", "instagram-scraper-api2.p.rapidapi.com"
)
RAPIDAPI_ENDPOINT_INSTAGRAM = os.getenv(
    "RAPIDAPI_ENDPOINT_INSTAGRAM", "/v1/hashtag"
)

# --- Score viral --------------------------------------------------------
# Vídeos com score >= threshold ficam marcados como "candidato"
SCORE_THRESHOLD = float(os.getenv("SCORE_THRESHOLD", "500"))
# Peso da taxa de engagement na fórmula do score
PESO_ENGAGEMENT = float(os.getenv("PESO_ENGAGEMENT", "10"))

# --- Armazenamento ------------------------------------------------------
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "radar_viral.db"))
DOWNLOADS_DIR = Path(os.getenv("DOWNLOADS_DIR", str(BASE_DIR / "downloads")))

# --- Dashboard ----------------------------------------------------------
FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
