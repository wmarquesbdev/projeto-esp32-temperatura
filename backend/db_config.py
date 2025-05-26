from pymongo import MongoClient
from datetime import datetime
import os
from dotenv import load_dotenv
import sys

load_dotenv()

def get_mongodb_connection():
    """Estabelece e retorna uma conexão com o MongoDB
    
    Returns:
        tuple: (client, db, collection) se a conexão for bem-sucedida, ou (None, None, None) caso contrário
    """
    try:
        mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
        print(f"Tentando conectar ao MongoDB em: {mongo_uri}")
        
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)

        client.server_info()
        print("Conexão com MongoDB estabelecida com sucesso!")
        
        db_name = os.getenv('MONGO_DB', 'temperatura_db')
        collection_name = os.getenv('MONGO_COLLECTION', 'leituras')
        
        db = client[db_name]
        collection = db[collection_name]
        
        collection.create_index([('timestamp', -1)])
        
        return client, db, collection
        
    except Exception as e:
        print(f"Erro ao conectar ao MongoDB: {e}", file=sys.stderr)
        print("Certifique-se de que o servidor MongoDB está em execução e que as credenciais estão corretas.")
        return None, None, None

if __name__ == "__main__":
    client, db, collection = get_mongodb_connection()
    
    if collection is not None:
        print(f"Conectado ao banco de dados: {db.name}")
        print(f"Usando coleção: {collection.name}")
        print(f"Número de documentos na coleção: {collection.count_documents({})}")
    else:
        print("Falha na conexão com o MongoDB.")