from contextlib import contextmanager
import psycopg
from psycopg.rows import dict_row
from pymongo import MongoClient
from src.config import get_settings


@contextmanager
def postgres_connection():
    settings = get_settings()
    conn = psycopg.connect(settings.postgres_dsn, row_factory=dict_row)
    try:
        yield conn
    finally:
        conn.close()


def mongo_database():
    settings = get_settings()
    client = MongoClient(settings.mongo_uri)
    return client[settings.mongo_db]