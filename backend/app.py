from flask import Flask, request, jsonify
from datetime import datetime
import sys

try:
    from db_config import get_mongodb_connection
except ImportError:
    print("ERRO: Não foi possível importar o módulo db_config. Verifique se o arquivo db_config.py está no mesmo diretório.")
    
    def get_mongodb_connection():
        print("Função de conexão com MongoDB não disponível.")
        return None, None, None

app = Flask(__name__)

_, _, collection = get_mongodb_connection()

@app.route('/data', methods=['POST'])
def receive_data():
    """Endpoint para receber dados de temperatura e umidade"""
    if collection is None:
        return jsonify({"status": "error", "message": "Banco de dados não disponível"}), 503
    
    try:
        data = request.json

        required_fields = ['temperatura', 'umidade']
        for field in required_fields:
            if field not in data:
                return jsonify({"status": "error", "message": f"Campo obrigatório ausente: {field}"}), 400
        
        try:
            temp = float(data['temperatura'])
            umid = float(data['umidade'])
            
            if not (-50 <= temp <= 100):
                return jsonify({"status": "error", "message": f"Temperatura fora do intervalo válido (-50°C a 100°C): {temp}"}), 400
            
            if not (0 <= umid <= 100):
                return jsonify({"status": "error", "message": f"Umidade fora do intervalo válido (0% a 100%): {umid}"}), 400
        except ValueError:
            return jsonify({"status": "error", "message": "Valores de temperatura ou umidade inválidos"}), 400
        
        data['timestamp'] = datetime.now()
        
        collection.insert_one(data)
        
        return jsonify({
            "status": "success", 
            "message": "Dados recebidos com sucesso",
            "data": {
                "temperatura": data['temperatura'],
                "umidade": data['umidade'],
                "timestamp": data['timestamp'].isoformat()
            }
        }), 200
        
    except Exception as e:
        return jsonify({"status": "error", "message": f"Erro ao processar dados: {str(e)}"}), 500

@app.route('/data', methods=['GET'])
def get_data():
    """Endpoint para recuperar dados de temperatura e umidade"""
    if collection is None:
        return jsonify({"status": "error", "message": "Banco de dados não disponível"}), 503
    
    try:
        limit = min(int(request.args.get('limit', 100)), 1000)
        skip = int(request.args.get('skip', 0))
        
        cursor = collection.find().sort('timestamp', -1).skip(skip).limit(limit)
        data = []
        
        for document in cursor:
            document['_id'] = str(document['_id'])
            if 'timestamp' in document and isinstance(document['timestamp'], datetime):
                document['timestamp'] = document['timestamp'].isoformat()
            data.append(document)
        
        return jsonify({
            "status": "success",
            "count": len(data),
            "data": data
        }), 200
        
    except Exception as e:
        return jsonify({"status": "error", "message": f"Erro ao recuperar dados: {str(e)}"}), 500

@app.route('/stats', methods=['GET'])
def get_stats():
    """Endpoint para estatísticas resumidas"""
    if collection is None:
        return jsonify({"status": "error", "message": "Banco de dados não disponível"}), 503
    
    try:
        temp_stats = collection.aggregate([
            {
                '$group': {
                    '_id': None,
                    'avg_temp': {'$avg': '$temperatura'},
                    'max_temp': {'$max': '$temperatura'},
                    'min_temp': {'$min': '$temperatura'},
                    'count': {'$sum': 1}
                }
            }
        ])
        
        umid_stats = collection.aggregate([
            {
                '$group': {
                    '_id': None,
                    'avg_umid': {'$avg': '$umidade'},
                    'max_umid': {'$max': '$umidade'},
                    'min_umid': {'$min': '$umidade'}
                }
            }
        ])
        
        temp_result = list(temp_stats)
        umid_result = list(umid_stats)
        
        if temp_result and umid_result:
            stats = {
                "temperatura": {
                    "média": round(temp_result[0]['avg_temp'], 2),
                    "máxima": temp_result[0]['max_temp'],
                    "mínima": temp_result[0]['min_temp']
                },
                "umidade": {
                    "média": round(umid_result[0]['avg_umid'], 2),
                    "máxima": umid_result[0]['max_umid'],
                    "mínima": umid_result[0]['min_umid']
                },
                "total_registros": temp_result[0]['count']
            }
            return jsonify({"status": "success", "stats": stats}), 200
        else:
            return jsonify({"status": "error", "message": "Não há dados suficientes para estatísticas"}), 404
            
    except Exception as e:
        return jsonify({"status": "error", "message": f"Erro ao calcular estatísticas: {str(e)}"}), 500

if __name__ == '__main__':
    if collection is None:
        print("AVISO: MongoDB não está disponível. A API terá funcionalidade limitada.")
        
    app.run(host='0.0.0.0', port=5000, debug=True)