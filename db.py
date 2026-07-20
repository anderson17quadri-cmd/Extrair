"""Acesso à base de dados SQLite do Radar Viral."""
import sqlite3
from contextlib import contextmanager

import config

SCHEMA_TABELA = """
CREATE TABLE IF NOT EXISTS videos (
    id              TEXT PRIMARY KEY,
    rede            TEXT NOT NULL DEFAULT 'tiktok',
    nicho           TEXT NOT NULL,
    autor           TEXT,
    username_autor  TEXT,
    descricao       TEXT,
    hashtags        TEXT,
    views           INTEGER DEFAULT 0,
    likes           INTEGER DEFAULT 0,
    comentarios     INTEGER DEFAULT 0,
    partilhas       INTEGER DEFAULT 0,
    data_publicacao TEXT,
    url_video       TEXT,
    url_download    TEXT,
    data_coleta     TEXT,
    score_viral     REAL,
    candidato       INTEGER DEFAULT 0,
    usado           INTEGER DEFAULT 0,
    ficheiro_local  TEXT,
    legenda_sugerida TEXT
);
"""

SCHEMA_INDICES = """
CREATE INDEX IF NOT EXISTS idx_videos_nicho ON videos (nicho);
CREATE INDEX IF NOT EXISTS idx_videos_candidato ON videos (candidato, score_viral);
CREATE INDEX IF NOT EXISTS idx_videos_rede ON videos (rede);
"""


@contextmanager
def ligacao():
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db():
    with ligacao() as con:
        con.executescript(SCHEMA_TABELA)
        # migração: bases de dados criadas antes da coluna "rede" existir
        colunas = [r["name"] for r in con.execute("PRAGMA table_info(videos)").fetchall()]
        if "rede" not in colunas:
            con.execute("ALTER TABLE videos ADD COLUMN rede TEXT NOT NULL DEFAULT 'tiktok'")
        con.executescript(SCHEMA_INDICES)


def inserir_video(video: dict) -> bool:
    """Insere um vídeo. Devolve False se já existia (duplicado ignorado)."""
    with ligacao() as con:
        cur = con.execute(
            """INSERT OR IGNORE INTO videos
               (id, rede, nicho, autor, username_autor, descricao, hashtags,
                views, likes, comentarios, partilhas,
                data_publicacao, url_video, url_download, data_coleta)
               VALUES (:id, :rede, :nicho, :autor, :username_autor, :descricao, :hashtags,
                       :views, :likes, :comentarios, :partilhas,
                       :data_publicacao, :url_video, :url_download, :data_coleta)""",
            video,
        )
        return cur.rowcount > 0
