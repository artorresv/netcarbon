from os import getenv
from dotenv import load_dotenv

load_dotenv('../.env')

DB_HOST = getenv('POSTGRES_HOST')
DB_PORT = getenv('POSTGRES_PORT') or 5432
DB_USER = getenv('POSTGRES_USER') or 'postgres'
DB_PASSWORD = getenv('POSTGRES_PASSWORD')
DB_NAME = getenv('POSTGRES_DB')
