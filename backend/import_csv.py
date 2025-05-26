import pandas as pd
from datetime import datetime
import sys
from pathlib import Path
import argparse
from utils import determinar_status

try:
    from db_config import get_mongodb_connection
except ImportError:
    print("ERRO: Não foi possível importar o módulo db_config. Verifique se o arquivo db_config.py está no mesmo diretório.")
    sys.exit(1)

try:
    from config import current_config
except ImportError:
    print("ERRO: Não foi possível importar o módulo config. Verifique se o arquivo config.py está no mesmo diretório.")
    sys.exit(1)

def limpar_colecao():
    """Limpa todos os documentos da coleção MongoDB"""
    try:
        client, db, collection = get_mongodb_connection()
        
        if collection is None:
            print("Não foi possível conectar ao MongoDB. Verifique a conexão.")
            return False
        
        print(f"Você está prestes a limpar a coleção: {collection.name} no banco de dados: {db.name}")
        confirmacao = input("Tem certeza que deseja continuar? (s/N): ")
        if confirmacao.lower() != 's':
            print("Operação de limpeza cancelada.")
            return False

        resultado = collection.delete_many({})
        print(f"Coleção limpa com sucesso! {resultado.deleted_count} documentos removidos.")
        return True
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Erro ao limpar a coleção: {e}")
        return False

def import_csv_to_mongodb(csv_path, adicionar_status=True):
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
        
        required_columns = ['temperatura', 'umidade']
        if not all(col in df.columns for col in required_columns):
            missing = [col for col in required_columns if col not in df.columns]
            print(f"Erro: Colunas necessárias ausentes no CSV: {missing}")
            return False
        
        if 'timestamp' in df.columns:
            print("Convertendo coluna timestamp...")
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            if df['timestamp'].isnull().any():
                print(f"Aviso: {df['timestamp'].isnull().sum()} timestamps não puderam ser convertidos e serão definidos como None ou removidos.")
        else:
            print("Coluna timestamp não encontrada, usando timestamp atual para cada registro.")
            df['timestamp'] = [datetime.now() for _ in range(len(df))]
        
        df['temperatura'] = pd.to_numeric(df['temperatura'], errors='coerce')
        df['umidade'] = pd.to_numeric(df['umidade'], errors='coerce')
        
        if adicionar_status:
            if 'status' not in df.columns:
                print("Adicionando coluna de status baseada nos valores...")
                df['status'] = df.apply(lambda row: determinar_status(row['temperatura'], row['umidade'], current_config), axis=1)
            else:
                print("Coluna de status já existe no CSV. Verificando e preenchendo valores ausentes se 'adicionar_status' for True...")
                df['status'] = df.apply(
                    lambda row: determinar_status(row['temperatura'], row['umidade'], current_config) if pd.isna(row.get('status')) else row.get('status'),
                    axis=1
                )

        invalid_temp = df['temperatura'].isna().sum()
        invalid_humid = df['umidade'].isna().sum()
        if invalid_temp > 0 or invalid_humid > 0:
            print(f"Aviso: Encontrados {invalid_temp} valores inválidos de temperatura e {invalid_humid} valores inválidos de umidade após conversão. Estes registros podem ter status 'erro_leitura'.")
        if df.empty:
            print("Aviso: Nenhum registro válido para importar após processamento.")
            return False

        records = df.to_dict('records')
        result = collection.insert_many(records)
        
        print(f"Importação concluída! {len(result.inserted_ids)} registros importados para o MongoDB.")
        return True
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Erro durante a importação: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Importar arquivo CSV para MongoDB')
    parser.add_argument('csv_path', type=str, help='Caminho para o arquivo CSV')
    parser.add_argument('--limpar', action='store_true', help='Limpar coleção antes de importar (PEDE CONFIRMAÇÃO)')
    parser.add_argument('--sem-status', action='store_false', dest='adicionar_status', help='Não adicionar/atualizar status automaticamente (padrão é adicionar/atualizar)')
    parser.set_defaults(adicionar_status=True)
    
    args = parser.parse_args()
    
    if args.limpar:
        print("Tentando limpar a coleção existente...")
        if not limpar_colecao():
            print("Não foi possível limpar a coleção ou a operação foi cancelada. Abortando.")
            sys.exit(1)
    
    print(f"Importando dados do arquivo: {args.csv_path}")
    success = import_csv_to_mongodb(args.csv_path, adicionar_status=args.adicionar_status)
    
    sys.exit(0 if success else 1)