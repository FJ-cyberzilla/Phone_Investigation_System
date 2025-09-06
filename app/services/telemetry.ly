import time
from datetime import datetime
from app.data.database import db
from app.data.models import InvestigationRequest, APIUsage

class TelemetryService:
    def __init__(self):
        self.requests = []
        self.api_usage = []
    
    def log_request(self, phone_number, module_name, success=True, response_time=0, user_id=None):
        """Log an investigation request"""
        try:
            request = InvestigationRequest(
                phone_number=phone_number,
                module=module_name,
                success=success,
                response_time=response_time,
                user_id=user_id,
                timestamp=datetime.utcnow()
            )
            db.session.add(request)
            db.session.commit()
        except Exception as e:
            print(f"Error logging request: {e}")
    
    def log_api_usage(self, api_name, endpoint, success=True, response_time=0):
        """Log API usage"""
        try:
            usage = APIUsage(
                api_name=api_name,
                endpoint=endpoint,
                success=success,
                response_time=response_time,
                timestamp=datetime.utcnow()
            )
            db.session.add(usage)
            db.session.commit()
        except Exception as e:
            print(f"Error logging API usage: {e}")
    
    def get_stats(self, hours=24):
        """Get statistics for the last specified hours"""
        try:
            # Get request statistics
            requests = InvestigationRequest.query.filter(
                InvestigationRequest.timestamp >= datetime.utcnow() - timedelta(hours=hours)
            ).all()
            
            # Get API usage statistics
            api_usage = APIUsage.query.filter(
                APIUsage.timestamp >= datetime.utcnow() - timedelta(hours=hours)
            ).all()
            
            return {
                'total_requests': len(requests),
                'successful_requests': sum(1 for r in requests if r.success),
                'average_response_time': sum(r.response_time for r in requests) / len(requests) if requests else 0,
                'api_usage': {api: sum(1 for u in api_usage if u.api_name == api) for api in set(u.api_name for u in api_usage)}
            }
        except Exception as e:
            print(f"Error getting stats: {e}")
            return {}
