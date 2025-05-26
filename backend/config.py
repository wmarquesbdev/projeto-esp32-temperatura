import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Classe de configuração centralizada"""
    
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
    MONGO_DB = os.getenv('MONGO_DB', 'temperatura_db')
    MONGO_COLLECTION = os.getenv('MONGO_COLLECTION', 'leituras')
    
    FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
    FLASK_PORT = int(os.getenv('FLASK_PORT', 5000))
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    STREAMLIT_SERVER_PORT = int(os.getenv('STREAMLIT_SERVER_PORT', 8501))
    STREAMLIT_SERVER_ADDRESS = os.getenv('STREAMLIT_SERVER_ADDRESS', '0.0.0.0')
    
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'app.log')
    
    TEMP_MIN_ALERTA = float(os.getenv('TEMP_MIN_ALERTA', 5))
    TEMP_MAX_ALERTA = float(os.getenv('TEMP_MAX_ALERTA', 30))
    TEMP_MIN_CRITICO = float(os.getenv('TEMP_MIN_CRITICO', 0))
    TEMP_MAX_CRITICO = float(os.getenv('TEMP_MAX_CRITICO', 40))
    
    UMID_MIN_ALERTA = float(os.getenv('UMID_MIN_ALERTA', 20))
    UMID_MAX_ALERTA = float(os.getenv('UMID_MAX_ALERTA', 90))
    UMID_MIN_CRITICO = float(os.getenv('UMID_MIN_CRITICO', 10))
    UMID_MAX_CRITICO = float(os.getenv('UMID_MAX_CRITICO', 95))
    
    BACKUP_ENABLED = os.getenv('BACKUP_ENABLED', 'false').lower() == 'true'
    BACKUP_INTERVAL_HOURS = int(os.getenv('BACKUP_INTERVAL_HOURS', 24))
    BACKUP_PATH = os.getenv('BACKUP_PATH', './backups/')
    
    EMAIL_ENABLED = os.getenv('EMAIL_ENABLED', 'false').lower() == 'true'
    EMAIL_SMTP_SERVER = os.getenv('EMAIL_SMTP_SERVER', 'smtp.gmail.com')
    EMAIL_SMTP_PORT = int(os.getenv('EMAIL_SMTP_PORT', 587))
    EMAIL_USERNAME = os.getenv('EMAIL_USERNAME', '')
    EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', '')
    EMAIL_RECIPIENTS = os.getenv('EMAIL_RECIPIENTS', '').split(',')
    
    API_KEY = os.getenv('API_KEY', '')
    
    @classmethod
    def get_limites_temperatura(cls):
        """Retorna os limites de temperatura"""
        return {
            'alerta': {'min': cls.TEMP_MIN_ALERTA, 'max': cls.TEMP_MAX_ALERTA},
            'critico': {'min': cls.TEMP_MIN_CRITICO, 'max': cls.TEMP_MAX_CRITICO}
        }
    
    @classmethod
    def get_limites_umidade(cls):
        """Retorna os limites de umidade"""
        return {
            'alerta': {'min': cls.UMID_MIN_ALERTA, 'max': cls.UMID_MAX_ALERTA},
            'critico': {'min': cls.UMID_MIN_CRITICO, 'max': cls.UMID_MAX_CRITICO}
        }
    
    @classmethod
    def validar_configuracao(cls):
        """Valida se as configurações estão corretas"""
        erros = []
        
        if cls.TEMP_MIN_CRITICO >= cls.TEMP_MIN_ALERTA:
            erros.append("TEMP_MIN_CRITICO deve ser menor que TEMP_MIN_ALERTA")
        
        if cls.TEMP_MAX_ALERTA >= cls.TEMP_MAX_CRITICO:
            erros.append("TEMP_MAX_ALERTA deve ser menor que TEMP_MAX_CRITICO")
        
        if cls.UMID_MIN_CRITICO >= cls.UMID_MIN_ALERTA:
            erros.append("UMID_MIN_CRITICO deve ser menor que UMID_MIN_ALERTA")
        
        if cls.UMID_MAX_ALERTA >= cls.UMID_MAX_CRITICO:
            erros.append("UMID_MAX_ALERTA deve ser menor que UMID_MAX_CRITICO")
        
        if cls.EMAIL_ENABLED:
            if not cls.EMAIL_USERNAME:
                erros.append("EMAIL_USERNAME é obrigatório quando EMAIL_ENABLED=true")
            if not cls.EMAIL_PASSWORD:
                erros.append("EMAIL_PASSWORD é obrigatório quando EMAIL_ENABLED=true")
            if not cls.EMAIL_RECIPIENTS or cls.EMAIL_RECIPIENTS == ['']:
                erros.append("EMAIL_RECIPIENTS é obrigatório quando EMAIL_ENABLED=true")
        
        return erros

class DevelopmentConfig(Config):
    """Configurações para desenvolvimento"""
    FLASK_DEBUG = True
    LOG_LEVEL = 'DEBUG'

class ProductionConfig(Config):
    """Configurações para produção"""
    FLASK_DEBUG = False
    LOG_LEVEL = 'WARNING'

class TestingConfig(Config):
    """Configurações para testes"""
    MONGO_DB = 'temperatura_db_test'
    FLASK_DEBUG = True
    LOG_LEVEL = 'DEBUG'

def get_config():
    """Retorna a configuração baseada na variável de ambiente"""
    env = os.getenv('FLASK_ENV', 'development').lower()
    
    if env == 'production':
        return ProductionConfig
    elif env == 'testing':
        return TestingConfig
    else:
        return DevelopmentConfig

current_config = get_config()