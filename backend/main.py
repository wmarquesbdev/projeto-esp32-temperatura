import logging
from flask import Flask, request, jsonify
from datetime import datetime
import sys
import os
from flask_cors import CORS
from functools import wraps

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from utils import determinar_status
from config import current_config
from db_config import get_mongodb_connection

errors = current_config.validar_configuracao()
if errors:
    print("ERROS DE CONFIGURAÇÃO ENCONTRADOS NA API FLASK:")
    for error in errors:
        print(f"- {error}")
    print("A API PODE NÃO FUNCIONAR CORRETAMENTE. Verifique seu arquivo .env ou variáveis de ambiente.")
app = Flask(__name__)
CORS(app)

client, db, collection = get_mongodb_connection()

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key_header = request.headers.get('X-API-KEY')
        api_key_query = request.args.get('api_key')

        if not current_config.API_KEY:
             return jsonify({"status": "error", "message": "Configuração de API Key ausente no servidor"}), 500


        if (api_key_header and api_key_header == current_config.API_KEY) or \
           (api_key_query and api_key_query == current_config.API_KEY):
            return f(*args, **kwargs)
        else:
            return jsonify({"status": "error", "message": "Chave de API inválida ou ausente"}), 403
    return decorated_function

@app.route('/')
def index():
    return jsonify({
        "nome": "API de Monitoramento de Temperatura e Umidade",
        "versao": "1.0",
        "endpoints": {
            "/data (POST)": "Recebe dados de temperatura e umidade. Protegido por API Key (X-API-KEY no header ou api_key como query param).",
            "/data (GET)": "Retorna dados históricos.",
            "/stats": "Retorna estatísticas resumidas."
        },
        "status_conexao_db": "online" if collection is not None else "database offline"
    })

@app.route('/data', methods=['POST'])
def receive_data():
    if collection is None:
        return jsonify({"status": "error", "message": "Banco de dados não disponível"}), 503
    
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "Payload JSON ausente ou inválido"}), 400
        print(f"Dados recebidos: {data}")

        required_fields = ['temperatura', 'umidade']
        for field in required_fields:
            if field not in data:
                return jsonify({"status": "error", "message": f"Campo obrigatório ausente: {field}"}), 400
        
        try:
            temp = float(data['temperatura'])
            umid = float(data['umidade'])
            
            if not (-50 <= temp <= 100):
                return jsonify({"status": "error", "message": f"Temperatura fora do intervalo físico válido (-50°C a 100°C): {temp}"}), 400
            
            if not (0 <= umid <= 100):
                return jsonify({"status": "error", "message": f"Umidade fora do intervalo físico válido (0% a 100%): {umid}"}), 400
        except (ValueError, TypeError):
            return jsonify({"status": "error", "message": "Valores de temperatura ou umidade inválidos. Devem ser numéricos."}), 400
        
        timestamp = data.get('timestamp')
        if timestamp:
            try:
                data['timestamp'] = datetime.fromisoformat(timestamp.replace("Z", "+00:00")) if isinstance(timestamp, str) else timestamp
            except ValueError:
                 return jsonify({"status": "error", "message": f"Formato de timestamp inválido: {timestamp}. Use ISO 8601."}), 400
        else:
            data['timestamp'] = datetime.now()
            
        data['status'] = determinar_status(temp, umid, current_config)
        
        collection.insert_one(data)
        
        response_data = data.copy()
        if isinstance(response_data.get('timestamp'), datetime):
            response_data['timestamp'] = response_data['timestamp'].isoformat()
        if '_id' in response_data:
            del response_data['_id']

        return jsonify({
            "status": "success", 
            "message": "Dados recebidos com sucesso",
            "data_stored": response_data
        }), 201
        
    except Exception as e:
        logger.error(f"Erro ao processar dados: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": f"Erro interno ao processar dados: {str(e)}"}), 500


@app.route('/data', methods=['GET'])
def get_data():
    if collection is None:
        return jsonify({"status": "error", "message": "Banco de dados não disponível"}), 503
    
    try:
        limit = min(int(request.args.get('limit', 100)), 1000)
        skip = int(request.args.get('skip', 0))
        
        query = {}
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        if start_date_str:
            try:
                start_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
                query.setdefault('timestamp', {})['$gte'] = start_date
            except ValueError:
                return jsonify({"status": "error", "message": "Formato de start_date inválido. Use ISO (YYYY-MM-DDTHH:MM:SS)"}), 400
        
        if end_date_str:
            try:
                end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                query.setdefault('timestamp', {})['$lte'] = end_date
            except ValueError:
                return jsonify({"status": "error", "message": "Formato de end_date inválido. Use ISO (YYYY-MM-DDTHH:MM:SS)"}), 400
        
        if 'status' in request.args:
            query['status'] = request.args.get('status')
        
        cursor = collection.find(query).sort('timestamp', -1).skip(skip).limit(limit)
        data_list = []
        
        for document in cursor:
            document['_id'] = str(document['_id'])
            if isinstance(document.get('timestamp'), datetime):
                document['timestamp'] = document['timestamp'].isoformat()
            data_list.append(document)
        
        total_count_in_query = collection.count_documents(query)

        return jsonify({
            "status": "success",
            "count_returned": len(data_list),
            "total_matching": total_count_in_query,
            "limit": limit,
            "skip": skip,
            "data": data_list
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao recuperar dados: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": f"Erro interno ao recuperar dados: {str(e)}"}), 500

@app.route('/stats', methods=['GET'])
def get_stats():
    if collection is None:
        return jsonify({"status": "error", "message": "Banco de dados não disponível"}), 503
    
    try:
        match_query = {}
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        if start_date_str:
            try:
                start_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
                match_query.setdefault('timestamp', {})['$gte'] = start_date
            except ValueError:
                return jsonify({"status": "error", "message": "Formato de start_date inválido. Use ISO (YYYY-MM-DDTHH:MM:SS)"}), 400
        
        if end_date_str:
            try:
                end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                match_query.setdefault('timestamp', {})['$lte'] = end_date
            except ValueError:
                return jsonify({"status": "error", "message": "Formato de end_date inválido. Use ISO (YYYY-MM-DDTHH:MM:SS)"}), 400
        
        pipeline = []
        if match_query:
            pipeline.append({'$match': match_query})
        
        pipeline.extend([
            {'$match': {'temperatura': {'$ne': None}, 'umidade': {'$ne': None}}},
            {
                '$group': {
                    '_id': None,
                    'avg_temp': {'$avg': '$temperatura'},
                    'max_temp': {'$max': '$temperatura'},
                    'min_temp': {'$min': '$temperatura'},
                    'avg_umid': {'$avg': '$umidade'},
                    'max_umid': {'$max': '$umidade'},
                    'min_umid': {'$min': '$umidade'},
                    'count': {'$sum': 1}
                }
            }
        ])
        
        stats_result = list(collection.aggregate(pipeline))
        
        status_pipeline = []
        if match_query:
            status_pipeline.append({'$match': match_query})
        status_pipeline.extend([
            {'$group': {'_id': '$status', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}}
        ])
        
        status_distribution_result = list(collection.aggregate(status_pipeline))
        
        status_counts = {item['_id']: item['count'] for item in status_distribution_result if item['_id']}

        if stats_result and stats_result[0]['count'] > 0:
            res = stats_result[0]
            stats_data = {
                "periodo_consultado": match_query.get("timestamp", "Todos os dados"),
                "temperatura": {
                    "media": round(res['avg_temp'], 2) if 'avg_temp' in res else None,
                    "maxima": res['max_temp'] if 'max_temp' in res else None,
                    "minima": res['min_temp'] if 'min_temp' in res else None,
                },
                "umidade": {
                    "media": round(res['avg_umid'], 2) if 'avg_umid' in res else None,
                    "maxima": res['max_umid'] if 'max_umid' in res else None,
                    "minima": res['min_umid'] if 'min_umid' in res else None,
                },
                "total_registros_validos_no_periodo": res['count'],
                "distribuicao_status_no_periodo": status_counts
            }
            if isinstance(stats_data["periodo_consultado"], dict):
                ts_dict = stats_data["periodo_consultado"]
                stats_data["periodo_consultado"] = {
                    k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in ts_dict.items()
                }

            return jsonify({"status": "success", "stats": stats_data}), 200
        else:
            return jsonify({"status": "success", "message": "Não há dados suficientes para estatísticas no período especificado ou com os filtros aplicados.", "stats": {
                "periodo_consultado": match_query.get("timestamp", "Todos os dados"),
                "total_registros_validos_no_periodo": 0,
                "distribuicao_status_no_periodo": status_counts
            }}), 200
            
    except Exception as e:
        logger.error(f"Erro ao calcular estatísticas: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": f"Erro interno ao calcular estatísticas: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', current_config.FLASK_PORT))
    debug_mode = current_config.FLASK_DEBUG
    
    if collection is None:
        print("AVISO: MongoDB não está disponível. A API terá funcionalidade limitada ou pode não iniciar.")
    
    print(f"Iniciando Flask API em host 0.0.0.0 porta {port} com debug={debug_mode}")
    app.run(host=current_config.FLASK_HOST, port=port, debug=debug_mode)