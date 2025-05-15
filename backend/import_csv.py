import pandas as pd
from datetime import datetime
import sys
from pathlib import Path

try:
    from db_config import get_mongodb_connection
except ImportError:
    print("ERRO: Não foi possível importar o módulo db_config. Verifique se o arquivo db_config.py está no mesmo diretório.")
    sys.exit(1)

def limpar_colecao():
    """Limpa todos os documentos da coleção MongoDB"""
    try:
        client, db, collection = get_mongodb_connection()
        
        if collection is None:
            print("Não foi possível conectar ao MongoDB. Verifique a conexão.")
            return False
        
        resultado = collection.delete_many({})
        print(f"Coleção limpa com sucesso! {resultado.deleted_count} documentos removidos.")
        return True
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Erro ao limpar a coleção: {e}")
        return False

def import_csv_to_mongodb(csv_path):
    """Importa dados de um arquivo CSV para o MongoDB"""
    csv_file = Path(csv_path)

    try:
        if not csv_file.exists():
            print(f"Erro: Arquivo '{csv_file}' não encontrado.")
            return False

        _, _, collection = get_mongodb_connection()
        
        if collection is None:
            print("Não foi possível conectar ao MongoDB. Verifique a conexão.")
            return False
        
        print(f"Lendo o arquivo: {csv_file}")
        df = pd.read_csv(csv_file)
        print(f"CSV carregado com sucesso: {len(df)} linhas.")
        
        # Adicionando 'status' às colunas obrigatórias
        required_columns = ['temperatura', 'umidade', 'status']
        if not all(col in df.columns for col in required_columns):
            missing = [col for col in required_columns if col not in df.columns]
            print(f"Erro: Colunas necessárias ausentes no CSV: {missing}")
            return False
        
        if 'timestamp' in df.columns:
            print("Convertendo coluna timestamp...")
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        else:
            print("Coluna timestamp não encontrada, usando timestamp atual.")
            df['timestamp'] = datetime.now()
        
        df['temperatura'] = pd.to_numeric(df['temperatura'], errors='coerce')
        df['umidade'] = pd.to_numeric(df['umidade'], errors='coerce')
        
        invalid_rows = df[(df['temperatura'].isna()) | (df['umidade'].isna())].shape[0]
        if invalid_rows > 0:
            print(f"Aviso: {invalid_rows} linhas com valores inválidos foram encontradas e serão removidas.")
            df = df.dropna(subset=['temperatura', 'umidade'])
        
        records = df.to_dict('records')
        
        if not records:
            print("Aviso: Nenhum registro válido para importar.")
            return False
        
        result = collection.insert_many(records)
        
        print(f"Importação concluída! {len(result.inserted_ids)} registros importados para o MongoDB.")
        return True
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Erro durante a importação: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python import_csv.py [--limpar] caminho_para_arquivo.csv")
        print("  --limpar: Limpa a coleção antes de importar (opcional)")
        sys.exit(1)
    
    limpar = False
    csv_path = ""
    
    if sys.argv[1] == "--limpar":
        limpar = True
        if len(sys.argv) < 3:
            print("Erro: Caminho do arquivo CSV não fornecido após --limpar")
            sys.exit(1)
        csv_path = sys.argv[2]
    else:
        csv_path = sys.argv[1]
    
    if limpar:
        print("Limpando a coleção existente...")
        if not limpar_colecao():
            sys.exit(1)
    
    print(f"Importando dados do arquivo: {csv_path}")
    success = import_csv_to_mongodb(csv_path)
    sys.exit(0 if success else 1)