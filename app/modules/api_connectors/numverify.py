import requests
from app.modules.base_module import BaseModule
from app.core.exceptions import APIException
from flask import current_app

class NumVerifyConnector(BaseModule):
    def __init__(self):
        super().__init__("numverify", rate_limit=100, rate_period=3600)
        self.base_url = "http://apilayer.net/api/validate"
    
    def execute(self, phone_number, **kwargs):
        try:
            self.check_rate_limit()
            
            params = {
                'access_key': current_app.config['NUMVERIFY_API_KEY'],
                'number': phone_number,
                'format': 1
            }
            
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if not data.get('valid'):
                return self.format_response({}, False, "Invalid phone number")
            
            return self.format_response({
                "valid": data['valid'],
                "number": data['number'],
                "local_format": data['local_format'],
                "international_format": data['international_format'],
                "country_prefix": data['country_prefix'],
                "country_code": data['country_code'],
                "country_name": data['country_name'],
                "location": data['location'],
                "carrier": data['carrier'],
                "line_type": data['line_type']
            })
            
        except requests.exceptions.RequestException as e:
            raise APIException(f"NumVerify API error: {str(e)}")
        except Exception as e:
            raise APIException(f"Unexpected error in NumVerify: {str(e)}")
