import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import logging
from config import current_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def determinar_status(temperatura, umidade, config=current_config):
    """
    Determina o status com base na temperatura e umidade usando os limites da configuração.
    
    Args:
        temperatura (float): Valor da temperatura em Celsius
        umidade (float): Valor da umidade em percentual
        config (Config): Objeto de configuração com os limites
        
    Returns:
        str: Status determinado
    """
    try:
        if pd.isna(temperatura) or pd.isna(umidade):
            return "erro_leitura"
        
        temp = float(temperatura)
        humid = float(umidade)
        
        if temp < -50 or temp > 100:
            return "erro_sensor"
        
        if humid < 0 or humid > 100:
            return "erro_sensor"

        if temp < config.TEMP_MIN_CRITICO or temp > config.TEMP_MAX_CRITICO:
            return "critico_temperatura"
        elif temp < config.TEMP_MIN_ALERTA or temp > config.TEMP_MAX_ALERTA:
            return "alerta_temperatura"
        
        if humid < config.UMID_MIN_CRITICO or humid > config.UMID_MAX_CRITICO:
            return "critico_umidade"
        elif humid < config.UMID_MIN_ALERTA or humid > config.UMID_MAX_ALERTA:
            return "alerta_umidade"
        
        return "normal"
        
    except (ValueError, TypeError) as e:
        logger.error(f"Erro ao determinar status: {e}")
        return "erro_leitura"

def validar_dados_sensor(temperatura, umidade):
    """
    Valida se os dados do sensor estão dentro de parâmetros aceitáveis
    
    Args:
        temperatura (float): Valor da temperatura
        umidade (float): Valor da umidade
        
    Returns:
        tuple: (bool, str) - (válido, mensagem de erro)
    """
    try:
        temp = float(temperatura)
        humid = float(umidade)
        
        if temp < -50 or temp > 100:
            return False, f"Temperatura fora da faixa válida (-50°C a 100°C): {temp}°C"
        
        if humid < 0 or humid > 100:
            return False, f"Umidade fora da faixa válida (0% a 100%): {humid}%"
        
        if temp == 0 and humid == 0:
            return False, "Valores suspeitos: temperatura e umidade ambos zero"
        
        return True, "Dados válidos"
        
    except (ValueError, TypeError):
        return False, "Valores não são números válidos"

def calcular_estatisticas(dados):
    if dados.empty:
        return {}
    
    stats = {}
    
    temp_valid = dados['temperatura'].dropna()
    if not temp_valid.empty:
        stats['temperatura'] = {
            'media': float(temp_valid.mean()),
            'mediana': float(temp_valid.median()),
            'minimo': float(temp_valid.min()),
            'maximo': float(temp_valid.max()),
            'desvio_padrao': float(temp_valid.std()),
            'count': len(temp_valid)
        }
    
    humid_valid = dados['umidade'].dropna()
    if not humid_valid.empty:
        stats['umidade'] = {
            'media': float(humid_valid.mean()),
            'mediana': float(humid_valid.median()),
            'minimo': float(humid_valid.min()),
            'maximo': float(humid_valid.max()),
            'desvio_padrao': float(humid_valid.std()),
            'count': len(humid_valid)
        }
    
    if 'status' in dados.columns:
        status_counts = dados['status'].value_counts().to_dict()
        stats['status_distribution'] = status_counts
    
    return stats

def gerar_relatorio_periodo(dados, periodo_horas=24):
    """
    Gera relatório para um período específico
    
    Args:
        dados (pd.DataFrame): DataFrame com os dados
        periodo_horas (int): Período em horas para o relatório
        
    Returns:
        dict: Relatório com estatísticas e alertas
    """
    if dados.empty:
        return {"erro": "Nenhum dado disponível"}
    
    agora = datetime.now()
    inicio_periodo = agora - timedelta(hours=periodo_horas)
    
    if 'timestamp' in dados.columns:
        dados_periodo = dados[dados['timestamp'] >= inicio_periodo].copy()
    else:
        dados_periodo = dados.copy()
    
    if dados_periodo.empty:
        return {"erro": f"Nenhum dado encontrado para as últimas {periodo_horas} horas"}
    
    relatorio = {
        'periodo': f"Últimas {periodo_horas} horas",
        'total_registros': len(dados_periodo),
        'inicio': inicio_periodo.strftime('%d/%m/%Y %H:%M'),
        'fim': agora.strftime('%d/%m/%Y %H:%M')
    }
    
    stats_calc = calcular_estatisticas(dados_periodo)
    relatorio.update(stats_calc)
    
    alertas = dados_periodo[dados_periodo['status'] != 'normal']
    relatorio['total_alertas'] = len(alertas)
    
    if not alertas.empty:
        relatorio['alertas_recentes'] = []
        for _, alerta in alertas.tail(5).iterrows():
            relatorio['alertas_recentes'].append({
                'timestamp': alerta['timestamp'].strftime('%d/%m/%Y %H:%M:%S') if 'timestamp' in alerta and pd.notna(alerta['timestamp']) else 'N/A',
                'status': alerta['status'],
                'temperatura': alerta['temperatura'],
                'umidade': alerta['umidade']
            })
    
    return relatorio

def detectar_anomalias(dados, janela=10, desvios=2):
    """
    Detecta anomalias nos dados usando desvio padrão móvel
    
    Args:
        dados (pd.DataFrame): DataFrame com os dados
        janela (int): Tamanho da janela para média móvel
        desvios (float): Número de desvios padrão para considerar anomalia
        
    Returns:
        pd.DataFrame: DataFrame com coluna adicional 'anomalia'
    """
    if dados.empty or len(dados) < janela:
        dados['anomalia'] = False
        return dados
    
    dados_copy = dados.copy()
    
    if 'temperatura' in dados_copy.columns:
        temp_media_movel = dados_copy['temperatura'].rolling(window=janela, min_periods=1).mean()
        temp_std_movel = dados_copy['temperatura'].rolling(window=janela, min_periods=1).std().fillna(0)
        
        temp_anomalia = (
            (dados_copy['temperatura'] > temp_media_movel + desvios * temp_std_movel) |
            (dados_copy['temperatura'] < temp_media_movel - desvios * temp_std_movel)
        )
    else:
        temp_anomalia = pd.Series([False] * len(dados_copy), index=dados_copy.index)
    
    if 'umidade' in dados_copy.columns:
        humid_media_movel = dados_copy['umidade'].rolling(window=janela, min_periods=1).mean()
        humid_std_movel = dados_copy['umidade'].rolling(window=janela, min_periods=1).std().fillna(0)
        
        humid_anomalia = (
            (dados_copy['umidade'] > humid_media_movel + desvios * humid_std_movel) |
            (dados_copy['umidade'] < humid_media_movel - desvios * humid_std_movel)
        )
    else:
        humid_anomalia = pd.Series([False] * len(dados_copy), index=dados_copy.index)
    
    dados_copy['anomalia'] = temp_anomalia | humid_anomalia
    
    return dados_copy

def converter_timestamp(timestamp_str):
    """
    Converte string de timestamp para objeto datetime
    
    Args:
        timestamp_str (str): String do timestamp
        
    Returns:
        datetime: Objeto datetime ou None se inválido
    """
    formatos = [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d %H:%M:%S.%f',
        '%Y-%m-%dT%H:%M:%S.%f',
        '%d/%m/%Y %H:%M:%S',
        '%d/%m/%Y %H:%M'
    ]
    
    for formato in formatos:
        try:
            return datetime.strptime(timestamp_str, formato)
        except (ValueError, TypeError):
            continue
    
    logger.warning(f"Não foi possível converter timestamp: {timestamp_str}")
    return None

def formatar_relatorio_txt(relatorio):
    """
    Formata relatório em texto simples
    
    Args:
        relatorio (dict): Dicionário com dados do relatório
        
    Returns:
        str: Relatório formatado em texto
    """
    if 'erro' in relatorio:
        return f"ERRO: {relatorio['erro']}"
    
    texto = []
    texto.append("=" * 50)
    texto.append("RELATÓRIO DE MONITORAMENTO AMBIENTAL")
    texto.append("=" * 50)
    texto.append(f"Período: {relatorio.get('periodo', 'N/A')}")
    texto.append(f"Total de registros: {relatorio.get('total_registros', 0)}")
    texto.append(f"Período (datas): {relatorio.get('inicio', 'N/A')} até {relatorio.get('fim', 'N/A')}")
    texto.append("")
    
    if 'temperatura' in relatorio and isinstance(relatorio['temperatura'], dict):
        temp_stats = relatorio['temperatura']
        texto.append("TEMPERATURA:")
        texto.append(f"  Média: {temp_stats.get('media', 0):.1f}°C")
        texto.append(f"  Mínima: {temp_stats.get('minimo', 0):.1f}°C")
        texto.append(f"  Máxima: {temp_stats.get('maximo', 0):.1f}°C")
        texto.append(f"  Desvio Padrão: {temp_stats.get('desvio_padrao', 0):.1f}°C")
        texto.append("")
    
    if 'umidade' in relatorio and isinstance(relatorio['umidade'], dict):
        humid_stats = relatorio['umidade']
        texto.append("UMIDADE:")
        texto.append(f"  Média: {humid_stats.get('media', 0):.1f}%")
        texto.append(f"  Mínima: {humid_stats.get('minimo', 0):.1f}%")
        texto.append(f"  Máxima: {humid_stats.get('maximo', 0):.1f}%")
        texto.append(f"  Desvio Padrão: {humid_stats.get('desvio_padrao', 0):.1f}%")
        texto.append("")

    texto.append(f"TOTAL DE ALERTAS: {relatorio.get('total_alertas', 0)}")
    
    if 'alertas_recentes' in relatorio and relatorio['alertas_recentes']:
        texto.append("ALERTAS RECENTES:")
        for alerta in relatorio['alertas_recentes']:
            temp_val = alerta.get('temperatura', float('nan'))
            umid_val = alerta.get('umidade', float('nan'))
            texto.append(f"  {alerta.get('timestamp', 'N/A')} - {alerta.get('status', 'N/A')} "
                        f"(T: {temp_val:.1f}°C, U: {umid_val:.1f}%)")
    
    texto.append("=" * 50)
    
    return "\n".join(texto)

STATUS_CORES = {
    'normal': '#28a745',
    'alerta_temperatura': '#ffc107',
    'critico_temperatura': '#dc3545',
    'erro_sensor': '#6c757d',
    'erro_leitura': '#17a2b8',
    'alerta_umidade': '#fd7e14',
    'critico_umidade': '#9c27b0'
}

STATUS_DESCRICOES = {
    'normal': 'Sistema operando normalmente',
    'alerta_temperatura': 'Temperatura em nível de alerta',
    'critico_temperatura': 'Temperatura em nível crítico',
    'erro_sensor': 'Falha no sensor de leitura',
    'erro_leitura': 'Erro na leitura de dados',
    'alerta_umidade': 'Umidade em nível de alerta',
    'critico_umidade': 'Umidade em nível crítico'
}