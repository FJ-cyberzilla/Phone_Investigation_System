import os
from datetime import timedelta

class ProductionConfig:
    # Basic settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'production-secret-key-change-in-production')
    DEBUG = False
    TESTING = False
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'postgresql://user:pass@localhost:5432/phone_investigation')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Redis
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    
    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    
    # Rate limiting
    RATE_LIMIT_STORAGE_URL = REDIS_URL
    RATE_LIMIT_STRATEGY = 'fixed-window'
    RATE_LIMIT_DEFAULT = "1000 per hour"
    
    # API Keys (loaded from environment variables)
    IPSTACK_API_KEY = os.environ.get('IPSTACK_API_KEY')
    NUMVERIFY_API_KEY = os.environ.get('NUMVERIFY_API_KEY')
    USERSTACK_API_KEY = os.environ.get('USERSTACK_API_KEY')
    SCRAPERAPI_KEY = os.environ.get('SCRAPERAPI_KEY')
    SHODAN_API_KEY = os.environ.get('SHODAN_API_KEY')
    MAILBOXLAYER_API_KEY = os.environ.get('MAILBOXLAYER_API_KEY')
    HUNTER_API_KEY = os.environ.get('HUNTER_API_KEY')
    
    # Security
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Logging
    LOG_LEVEL = 'INFO'
    LOG_FILE = '/var/log/phone-investigation/app.log'
