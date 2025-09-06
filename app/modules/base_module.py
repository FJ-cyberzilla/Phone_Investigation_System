from abc import ABC, abstractmethod
from app.core.exceptions import RateLimitException, APIException
import time
import logging

logger = logging.getLogger(__name__)

class BaseModule(ABC):
    def __init__(self, name, rate_limit=10, rate_period=60):
        self.name = name
        self.rate_limit = rate_limit
        self.rate_period = rate_period
        self.request_times = []
    
    def check_rate_limit(self):
        now = time.time()
        # Remove old requests
        self.request_times = [t for t in self.request_times if now - t < self.rate_period]
        
        if len(self.request_times) >= self.rate_limit:
            raise RateLimitException(f"Rate limit exceeded for {self.name}")
        
        self.request_times.append(now)
        return True
    
    @abstractmethod
    def execute(self, phone_number, **kwargs):
        pass
    
    def format_response(self, data, success=True, error=None):
        return {
            "module": self.name,
            "success": success,
            "data": data,
            "error": error,
            "timestamp": time.time()
        }
