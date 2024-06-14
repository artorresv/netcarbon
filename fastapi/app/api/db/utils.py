from enum import Enum
import logging
from databases import Database
from utils.env import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME


class ProductName(str, Enum):
    ndvi = 'ndvi'
    ndmi = 'ndmi'


class FileFormat(str, Enum):
    tiff = 'tiff'
    png = 'png'


DATABASE_URL = f'postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'

database = Database(DATABASE_URL, min_size=5, max_size=20)


def get_database() -> Database:
    logging.info(DATABASE_URL)
    return database
