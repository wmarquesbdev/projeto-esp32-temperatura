from pymongo import MongoClient
from datetime import datetime
import os
from dotenv import load_dotenv
import sys

load_dotenv()

def get_mongodb_connection():
    """Estabelece e retorna uma conexão com o MongoDB"""
    try:
        mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
        print(f"Tentando conectar ao MongoDB em: {mongo_uri}")
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)

        client.server_info()
        print("Conexão com MongoDB estabelecida com sucesso!")
        
        db = client['temperatura_db']
        collection = db['leituras']
        
        return client, db, collection
        
    except Exception as e:
        print(f"Erro ao conectar ao MongoDB: {e}", file=sys.stderr)
        print("Certifique-se de que o servidor MongoDB está em execução.")
        return None, None, None