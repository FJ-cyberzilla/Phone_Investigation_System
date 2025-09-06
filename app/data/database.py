# app/data/database.py
import os
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Generator

from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session, relationship, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from sqlalchemy import event
from sqlalchemy import func, distinct

import redis
from redis.exceptions import RedisError

from app.core.config import Config
from app.core.exceptions import DatabaseError, CacheError

# Configure logging
logger = logging.getLogger(__name__)

# Database base class
Base = declarative_base()

class InvestigationRequest(Base):
    """Model for storing investigation requests"""
    __tablename__ = 'investigation_requests'
    
    id = Column(String(36), primary_key=True, unique=True, nullable=False)
    phone_number = Column(String(20), nullable=False, index=True)
    user_id = Column(String(36), nullable=True, index=True)
    session_id = Column(String(36), nullable=True, index=True)
    status = Column(String(20), default='pending', nullable=False)  # pending, processing, completed, failed
    modules_requested = Column(JSON, default=list)
    modules_completed = Column(JSON, default=list)
    results = Column(JSON, default=dict)
    error = Column(Text, nullable=True)
    processing_time = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    priority = Column(Integer, default=1)  # 1-10, higher is more urgent
    
    # Indexes
    __table_args__ = (
        Index('ix_investigation_requests_phone_number', 'phone_number'),
        Index('ix_investigation_requests_user_id', 'user_id'),
        Index('ix_investigation_requests_status', 'status'),
        Index('ix_investigation_requests_created_at', 'created_at'),
    )

class APIUsage(Base):
    """Model for tracking API usage and rate limiting"""
    __tablename__ = 'api_usage'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    api_name = Column(String(50), nullable=False, index=True)
    endpoint = Column(String(100), nullable=False)
    phone_number = Column(String(20), nullable=True, index=True)
    user_id = Column(String(36), nullable=True, index=True)
    success = Column(Boolean, default=True)
    response_time = Column(Float, default=0.0)
    status_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    cost = Column(Float, default=0.0)  # API call cost in USD
    
    # Indexes
    __table_args__ = (
        Index('ix_api_usage_api_name', 'api_name'),
        Index('ix_api_usage_timestamp', 'timestamp'),
        Index('ix_api_usage_user_id', 'user_id'),
    )

class User(Base):
    """Model for system users"""
    __tablename__ = 'users'
    
    id = Column(String(36), primary_key=True, unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    api_key = Column(String(255), unique=True, nullable=True)
    rate_limit = Column(Integer, default=100)  # Requests per hour
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    investigations = relationship('InvestigationRequest', backref='user', lazy='dynamic')
    api_usage = relationship('APIUsage', backref='user', lazy='dynamic')

class SystemConfig(Base):
    """Model for system configuration"""
    __tablename__ = 'system_config'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(JSON, nullable=False)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String(36), ForeignKey('users.id'), nullable=True)

class CacheEntry(Base):
    """Model for persistent cache storage"""
    __tablename__ = 'cache_entries'
    
    key = Column(String(255), primary_key=True, nullable=False)
    value = Column(JSON, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    accessed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    access_count = Column(Integer, default=0)

class DatabaseManager:
    """Database management class with connection pooling and utilities"""
    
    def __init__(self, config: Config):
        self.config = config
        self.engine = None
        self.session_factory = None
        self.redis_client = None
        self.is_connected = False
        
    def init_app(self, app):
        """Initialize database with Flask app"""
        try:
            # Setup SQLAlchemy
            database_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
            pool_size = app.config.get('SQLALCHEMY_POOL_SIZE', 20)
            max_overflow = app.config.get('SQLALCHEMY_MAX_OVERFLOW', 10)
            pool_timeout = app.config.get('SQLALCHEMY_POOL_TIMEOUT', 30)
            pool_recycle = app.config.get('SQLALCHEMY_POOL_RECYCLE', 1800)
            
            self.engine = create_engine(
                database_uri,
                poolclass=QueuePool,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_timeout=pool_timeout,
                pool_recycle=pool_recycle,
                echo=app.config.get('SQLALCHEMY_ECHO', False),
                connect_args={"connect_timeout": 30}
            )
            
            # Create session factory
            self.session_factory = sessionmaker(bind=self.engine)
            self.Session = scoped_session(self.session_factory)
            
            # Setup Redis
            redis_url = app.config.get('REDIS_URL')
            if redis_url:
                self.redis_client = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True
                )
            
            self.is_connected = True
            logger.info("Database connection established successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
            raise DatabaseError(f"Database initialization failed: {str(e)}")
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get a database session with automatic cleanup"""
        session = self.Session()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database session error: {str(e)}")
            raise DatabaseError(f"Database operation failed: {str(e)}")
        finally:
            session.close()
    
    def health_check(self) -> Dict[str, Any]:
        """Check database health status"""
        try:
            with self.get_session() as session:
                # Test database connection
                session.execute('SELECT 1')
                db_status = 'healthy'
                
                # Test Redis connection if available
                redis_status = 'not_configured'
                if self.redis_client:
                    try:
                        self.redis_client.ping()
                        redis_status = 'healthy'
                    except RedisError:
                        redis_status = 'unhealthy'
                
                # Get some stats
                total_investigations = session.query(func.count(InvestigationRequest.id)).scalar()
                today_investigations = session.query(func.count(InvestigationRequest.id)).filter(
                    InvestigationRequest.created_at >= datetime.utcnow().date()
                ).scalar()
                
                return {
                    'database': db_status,
                    'redis': redis_status,
                    'stats': {
                        'total_investigations': total_investigations,
                        'today_investigations': today_investigations
                    },
                    'timestamp': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                'database': 'unhealthy',
                'redis': 'unknown',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def get_investigation(self, investigation_id: str) -> Optional[InvestigationRequest]:
        """Get investigation by ID"""
        try:
            with self.get_session() as session:
                return session.query(InvestigationRequest).filter_by(id=investigation_id).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting investigation {investigation_id}: {str(e)}")
            return None
    
    def create_investigation(self, phone_number: str, user_id: Optional[str] = None, 
                           session_id: Optional[str] = None, modules: List[str] = None) -> Optional[str]:
        """Create a new investigation request"""
        try:
            from uuid import uuid4
            
            investigation_id = str(uuid4())
            investigation = InvestigationRequest(
                id=investigation_id,
                phone_number=phone_number,
                user_id=user_id,
                session_id=session_id,
                modules_requested=modules or [],
                status='pending'
            )
            
            with self.get_session() as session:
                session.add(investigation)
                session.flush()
                return investigation_id
                
        except SQLAlchemyError as e:
            logger.error(f"Error creating investigation: {str(e)}")
            return None
    
    def update_investigation_results(self, investigation_id: str, results: Dict[str, Any], 
                                   module_name: str, processing_time: float = 0.0) -> bool:
        """Update investigation results for a specific module"""
        try:
            with self.get_session() as session:
                investigation = session.query(InvestigationRequest).filter_by(id=investigation_id).first()
                if not investigation:
                    return False
                
                # Update results
                if not investigation.results:
                    investigation.results = {}
                
                investigation.results[module_name] = results
                
                # Update completed modules
                if module_name not in investigation.modules_completed:
                    investigation.modules_completed.append(module_name)
                
                # Update processing time
                investigation.processing_time += processing_time
                
                # Check if all modules are completed
                if set(investigation.modules_requested) == set(investigation.modules_completed):
                    investigation.status = 'completed'
                    investigation.completed_at = datetime.utcnow()
                
                session.add(investigation)
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Error updating investigation results: {str(e)}")
            return False
    
    def log_api_usage(self, api_name: str, endpoint: str, success: bool = True, 
                     response_time: float = 0.0, status_code: Optional[int] = None,
                     error_message: Optional[str] = None, cost: float = 0.0,
                     phone_number: Optional[str] = None, user_id: Optional[str] = None) -> bool:
        """Log API usage for monitoring and billing"""
        try:
            usage = APIUsage(
                api_name=api_name,
                endpoint=endpoint,
                phone_number=phone_number,
                user_id=user_id,
                success=success,
                response_time=response_time,
                status_code=status_code,
                error_message=error_message,
                cost=cost,
                timestamp=datetime.utcnow()
            )
            
            with self.get_session() as session:
                session.add(usage)
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Error logging API usage: {str(e)}")
            return False
    
    def get_api_usage_stats(self, hours: int = 24, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get API usage statistics for monitoring"""
        try:
            with self.get_session() as session:
                since = datetime.utcnow() - timedelta(hours=hours)
                
                query = session.query(
                    APIUsage.api_name,
                    func.count(APIUsage.id).label('total_calls'),
                    func.avg(APIUsage.response_time).label('avg_response_time'),
                    func.sum(APIUsage.cost).label('total_cost'),
                    func.sum(case((APIUsage.success == True, 1), else_=0)).label('successful_calls'),
                    func.sum(case((APIUsage.success == False, 1), else_=0)).label('failed_calls')
                ).filter(APIUsage.timestamp >= since)
                
                if user_id:
                    query = query.filter(APIUsage.user_id == user_id)
                
                stats = query.group_by(APIUsage.api_name).all()
                
                return {
                    'period_hours': hours,
                    'stats': [
                        {
                            'api_name': row.api_name,
                            'total_calls': row.total_calls,
                            'successful_calls': row.successful_calls,
                            'failed_calls': row.failed_calls,
                            'success_rate': (row.successful_calls / row.total_calls * 100) if row.total_calls > 0 else 0,
                            'avg_response_time': float(row.avg_response_time or 0),
                            'total_cost': float(row.total_cost or 0)
                        }
                        for row in stats
                    ],
                    'timestamp': datetime.utcnow().isoformat()
                }
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting API usage stats: {str(e)}")
            return {'error': str(e)}
    
    # Redis cache methods
    def cache_get(self, key: str) -> Optional[Any]:
        """Get value from Redis cache"""
        if not self.redis_client:
            return None
            
        try:
            value = self.redis_client.get(key)
            return value if value is None else value
        except RedisError as e:
            logger.error(f"Redis get error for key {key}: {str(e)}")
            return None
    
    def cache_set(self, key: str, value: Any, expire: int = 3600) -> bool:
        """Set value in Redis cache with expiration"""
        if not self.redis_client:
            return False
            
        try:
            self.redis_client.setex(key, expire, value)
            return True
        except RedisError as e:
            logger.error(f"Redis set error for key {key}: {str(e)}")
            return False
    
    def cache_delete(self, key: str) -> bool:
        """Delete key from Redis cache"""
        if not self.redis_client:
            return False
            
        try:
            self.redis_client.delete(key)
            return True
        except RedisError as e:
            logger.error(f"Redis delete error for key {key}: {str(e)}")
            return False
    
    def cache_keys(self, pattern: str = '*') -> List[str]:
        """Get keys matching pattern from Redis cache"""
        if not self.redis_client:
            return []
            
        try:
            return self.redis_client.keys(pattern)
        except RedisError as e:
            logger.error(f"Redis keys error for pattern {pattern}: {str(e)}")
            return []

# Global database instance
db_manager = DatabaseManager(Config)

def init_db(app):
    """Initialize database with Flask app"""
    db_manager.init_app(app)
    
    # Create tables if they don't exist
    try:
        with app.app_context():
            Base.metadata.create_all(db_manager.engine)
            logger.info("Database tables created/verified successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {str(e)}")
        raise DatabaseError(f"Table creation failed: {str(e)}")

def get_db_session():
    """Get a database session for use in routes"""
    return db_manager.get_session()

# Database event listeners
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign keys for SQLite"""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

@event.listens_for(Session, "after_commit")
def update_cache_after_commit(session):
    """Example: Update cache after database commits"""
    # This would be implemented based on specific caching needs
    pass
