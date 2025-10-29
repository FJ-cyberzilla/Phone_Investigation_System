from flask import Blueprint, request, jsonify, current_app
import logging
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from app.modules import module_manager
from app.services.telemetry import TelemetryService
from app.services.security import validate_phone_number
from app.core.exceptions import InvalidInputException

bp = Blueprint('api', __name__)
limiter = Limiter(key_func=get_remote_address)
telemetry = TelemetryService()

@bp.route('/investigate', methods=['POST'])
@limiter.limit("10 per minute")
def investigate():
    try:
        data = request.get_json()
        phone_number = data.get('phone_number')
        
        if not phone_number:
            return jsonify({'error': 'Phone number is required'}), 400
        
        # Validate phone number
        if not validate_phone_number(phone_number):
            raise InvalidInputException("Invalid phone number format")
        
        # Get requested modules or use all
        modules = data.get('modules', ['all'])
        if 'all' in modules:
            modules = ['phone_info', 'social_media', 'spam_risk', 'web_search']
        
        results = {}
        for module_name in modules:
            try:
                start_time = time.time()
                module_result = module_manager.execute_module(module_name, phone_number)
                response_time = time.time() - start_time
                
                # Log telemetry
                telemetry.log_request(phone_number, module_name, True, response_time)
                
                results[module_name] = module_result
            except Exception as e:
                telemetry.log_request(phone_number, module_name, False, 0)
                results[module_name] = {'error': str(e)}
        
        # Perform AI analysis
        ai_analysis = current_app.ai_analyzer.analyze(results)
        results['ai_analysis'] = ai_analysis
        
        return jsonify({
            'success': True,
            'phone_number': phone_number,
            'results': results,
            'timestamp': time.time()
        })
        
    except InvalidInputException as e:
        return jsonify({'error': 'Invalid input'}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/stats', methods=['GET'])
def get_stats():
    try:
        hours = request.args.get('hours', 24, type=int)
        stats = telemetry.get_stats(hours)
        return jsonify({'stats': stats})
    except Exception as e:
        logging.exception("Error occurred while fetching stats")
        return jsonify({'error': 'Internal server error'}), 500
