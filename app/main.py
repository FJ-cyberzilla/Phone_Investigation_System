import os
import re
import time
import threading
import asyncio
import json
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from functools import wraps
import phonenumbers
from phonenumbers import geocoder, carrier, timezone
import pytz
import requests
from bs4 import BeautifulSoup
import numpy as np
from collections import defaultdict, Counter
import heapq
import math

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configuration
class Config:
    SESSION_TIMEOUT = 3600
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    RATE_LIMIT_REQUESTS = 10  # Max requests
    RATE_LIMIT_PERIOD = 60    # Period in seconds
    MODULES_DIR = "modules"
    CACHE_EXPIRY = 300        # 5 minutes

app.config.from_object(Config)

# Rate limiting
class RateLimiter:
    def __init__(self):
        self.requests = defaultdict(list)
    
    def is_allowed(self, identifier):
        now = time.time()
        self.requests[identifier] = [req_time for req_time in self.requests[identifier] 
                                    if now - req_time < app.config['RATE_LIMIT_PERIOD']]
        
        if len(self.requests[identifier]) < app.config['RATE_LIMIT_REQUESTS']:
            self.requests[identifier].append(now)
            return True
        return False

rate_limiter = RateLimiter()

# Decorators
def phone_number_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'phone_number' not in session:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def rate_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        identifier = session.get('phone_number', request.remote_addr)
        if not rate_limiter.is_allowed(identifier):
            return jsonify({"error": "Rate limit exceeded. Try again later."}), 429
        return f(*args, **kwargs)
    return decorated_function

# Cache system
class Cache:
    def __init__(self):
        self.cache = {}
    
    def get(self, key):
        if key in self.cache:
            data, expiry = self.cache[key]
            if time.time() < expiry:
                return data
            else:
                del self.cache[key]
        return None
    
    def set(self, key, data, expiry=None):
        if expiry is None:
            expiry = app.config['CACHE_EXPIRY']
        self.cache[key] = (data, time.time() + expiry)

cache = Cache()

# Entropy and pattern analysis
class PatternAnalyzer:
    @staticmethod
    def calculate_entropy(s):
        """Calculate Shannon entropy of a string"""
        if not s:
            return 0
        entropy = 0
        for x in range(256):
            p_x = float(s.count(chr(x))) / len(s)
            if p_x > 0:
                entropy += - p_x * math.log(p_x, 2)
        return entropy

    @staticmethod
    def analyze_phone_pattern(phone_number):
        """Analyze patterns in phone numbers"""
        digits = re.sub(r'\D', '', phone_number)
        patterns = []
        
        # Check for repeated digits
        digit_counts = Counter(digits)
        repeated_digits = [d for d, count in digit_counts.items() if count > len(digits)/2]
        if repeated_digits:
            patterns.append(f"Repeated digits: {', '.join(repeated_digits)}")
        
        # Check for sequential patterns
        sequences = PatternAnalyzer.find_sequences(digits)
        if sequences:
            patterns.append(f"Sequences found: {', '.join(sequences)}")
        
        # Check if it's a potential virtual number
        virtual_patterns = ['123', '000', '111', '222', '333', '444', '555', '666', '777', '888', '999']
        if any(pattern in digits for pattern in virtual_patterns):
            patterns.append("Contains virtual number patterns")
        
        return patterns
    
    @staticmethod
    def find_sequences(digits):
        """Find sequential patterns in digits"""
        sequences = []
        for i in range(len(digits) - 2):
            # Check ascending
            if (int(digits[i]) + 1 == int(digits[i+1]) and 
                int(digits[i+1]) + 1 == int(digits[i+2])):
                sequences.append(f"{digits[i]}{digits[i+1]}{digits[i+2]}")
            # Check descending
            elif (int(digits[i]) - 1 == int(digits[i+1]) and 
                  int(digits[i+1]) - 1 == int(digits[i+2])):
                sequences.append(f"{digits[i]}{digits[i+1]}{digits[i+2]}")
        return sequences

# AI Reasoning Engine
class AIReasoningEngine:
    def __init__(self):
        self.rules = self.load_rules()
    
    def load_rules(self):
        """Load reasoning rules from file or default"""
        rules_file = os.path.join(app.config['MODULES_DIR'], 'reasoning_rules.json')
        if os.path.exists(rules_file):
            with open(rules_file, 'r') as f:
                return json.load(f)
        
        # Default rules
        return {
            "high_entropy": {
                "threshold": 3.5,
                "message": "High entropy detected - may be a generated or virtual number",
                "risk": "medium"
            },
            "repeated_digits": {
                "message": "Repeated digit pattern detected - may be a virtual number",
                "risk": "low"
            },
            "sequential_digits": {
                "message": "Sequential digit pattern detected - may be a virtual number",
                "risk": "low"
            },
            "toll_free": {
                "patterns": ["800", "888", "877", "866", "855", "844", "833"],
                "message": "Toll-free number detected",
                "risk": "low"
            },
            "premium_rate": {
                "patterns": ["900", "976"],
                "message": "Premium rate number detected",
                "risk": "high"
            }
        }
    
    def analyze(self, phone_data):
        """Perform AI reasoning on phone data"""
        insights = []
        risks = []
        
        # Analyze entropy
        digits = re.sub(r'\D', '', phone_data['phone_number'])
        entropy = PatternAnalyzer.calculate_entropy(digits)
        
        if entropy > self.rules['high_entropy']['threshold']:
            insights.append(self.rules['high_entropy']['message'])
            risks.append(self.rules['high_entropy']['risk'])
        
        # Check for toll-free numbers
        for pattern in self.rules['toll_free']['patterns']:
            if pattern in digits:
                insights.append(self.rules['toll_free']['message'])
                risks.append(self.rules['toll_free']['risk'])
                break
        
        # Check for premium rate numbers
        for pattern in self.rules['premium_rate']['patterns']:
            if pattern in digits:
                insights.append(self.rules['premium_rate']['message'])
                risks.append(self.rules['premium_rate']['risk'])
                break
        
        # Determine overall risk
        overall_risk = "low"
        if "high" in risks:
            overall_risk = "high"
        elif "medium" in risks:
            overall_risk = "medium"
        
        return {
            "insights": insights,
            "entropy": entropy,
            "risk_level": overall_risk,
            "pattern_analysis": PatternAnalyzer.analyze_phone_pattern(phone_data['phone_number'])
        }

# Telemetry
class Telemetry:
    def __init__(self):
        self.requests = []
        self.errors = []
    
    def log_request(self, phone_number, module, success=True, response_time=0):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "phone_number": phone_number,
            "module": module,
            "success": success,
            "response_time": response_time
        }
        self.requests.append(entry)
        # Keep only last 1000 requests
        if len(self.requests) > 1000:
            self.requests = self.requests[-1000:]
    
    def log_error(self, phone_number, module, error_message):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "phone_number": phone_number,
            "module": module,
            "error": error_message
        }
        self.errors.append(entry)
        # Keep only last 100 errors
        if len(self.errors) > 100:
            self.errors = self.errors[-100:]
    
    def get_stats(self):
        total = len(self.requests)
        successful = sum(1 for r in self.requests if r['success'])
        error_rate = (total - successful) / total * 100 if total > 0 else 0
        
        # Calculate average response time
        avg_time = sum(r['response_time'] for r in self.requests) / total if total > 0 else 0
        
        return {
            "total_requests": total,
            "successful_requests": successful,
            "error_rate": f"{error_rate:.2f}%",
            "avg_response_time": f"{avg_time:.2f}s",
            "recent_errors": self.errors[-10:] if self.errors else []
        }

telemetry = Telemetry()

# Base module class
class InvestigationModule:
    def __init__(self, name):
        self.name = name
        self.rate_limited = False
        self.rate_limit_reset = 0
    
    def check_rate_limit(self):
        if self.rate_limited and time.time() < self.rate_limit_reset:
            raise Exception(f"Module {self.name} is rate limited. Try again later.")
        return True
    
    def handle_rate_limit(self, reset_time=60):
        self.rate_limited = True
        self.rate_limit_reset = time.time() + reset_time
        telemetry.log_error("system", self.name, "Rate limit hit")
    
    def execute(self, phone_number):
        start_time = time.time()
        try:
            self.check_rate_limit()
            result = self._execute(phone_number)
            response_time = time.time() - start_time
            telemetry.log_request(phone_number, self.name, True, response_time)
            return result
        except Exception as e:
            response_time = time.time() - start_time
            telemetry.log_request(phone_number, self.name, False, response_time)
            telemetry.log_error(phone_number, self.name, str(e))
            raise
    
    def _execute(self, phone_number):
        # To be implemented by subclasses
        raise NotImplementedError("Subclasses must implement this method")

# Phone number investigation module
class PhoneNumberModule(InvestigationModule):
    def __init__(self):
        super().__init__("phone_info")
    
    def _execute(self, phone_number):
        parsed_number = phonenumbers.parse(phone_number, None)
        is_valid = phonenumbers.is_valid_number(parsed_number)
        
        if not is_valid:
            return {"error": "Invalid phone number"}
        
        # Get timezones
        timezones = timezone.time_zones_for_number(parsed_number)
        
        # Get country and operator
        country = geocoder.description_for_number(parsed_number, "en")
        operator = carrier.name_for_number(parsed_number, "en")
        
        # Get current time if timezone is available
        current_time = None
        if timezones and timezones[0] != "Etc/Unknown":
            tz = pytz.timezone(timezones[0])
            datetime_in_tz = datetime.now(tz)
            current_time = datetime_in_tz.strftime('%Y-%m-%d %H:%M:%S %Z')
        
        return {
            'is_valid': is_valid,
            'country': country or "Unknown",
            'operator': operator or "Unknown",
            'timezones': timezones,
            'current_time': current_time or "Unknown",
            'number_type': self._get_number_type(parsed_number)
        }
    
    def _get_number_type(self, parsed_number):
        try:
            if carrier.name_for_number(parsed_number, "en"):
                return "Mobile"
            return "Landline"
        except:
            return "Unknown"

# Social media investigation module (simulated)
class SocialMediaModule(InvestigationModule):
    def __init__(self):
        super().__init__("social_media")
        self.platforms = {
            "facebook": self.check_facebook,
            "instagram": self.check_instagram,
            "twitter": self.check_twitter,
            "linkedin": self.check_linkedin
        }
    
    def _execute(self, phone_number):
        results = {}
        for platform, check_func in self.platforms.items():
            try:
                results[platform] = check_func(phone_number)
                # Simulate rate limiting
                time.sleep(0.5)
            except Exception as e:
                results[platform] = {"error": str(e)}
        
        return results
    
    def check_facebook(self, phone_number):
        # Simulated Facebook check
        return {
            "found": False,
            "profiles": [],
            "message": "Facebook API access required for real implementation"
        }
    
    def check_instagram(self, phone_number):
        # Simulated Instagram check
        return {
            "found": False,
            "profiles": [],
            "message": "Instagram API access required for real implementation"
        }
    
    def check_twitter(self, phone_number):
        # Simulated Twitter check
        return {
            "found": False,
            "profiles": [],
            "message": "Twitter API access required for real implementation"
        }
    
    def check_linkedin(self, phone_number):
        # Simulated LinkedIn check
        return {
            "found": False,
            "profiles": [],
            "message": "LinkedIn API access required for real implementation"
        }

# Spam risk assessment module
class SpamRiskModule(InvestigationModule):
    def __init__(self):
        super().__init__("spam_risk")
        self.known_spam_prefixes = ["800", "900", "976", "855", "866", "877", "888"]
    
    def _execute(self, phone_number):
        digits = re.sub(r'\D', '', phone_number)
        risk_score = 0
        reasons = []
        
        # Check if number is valid
        try:
            parsed = phonenumbers.parse(phone_number, None)
            if not phonenumbers.is_valid_number(parsed):
                risk_score += 30
                reasons.append("Invalid phone number format")
        except:
            risk_score += 50
            reasons.append("Cannot parse phone number")
        
        # Check against known spam prefixes
        for prefix in self.known_spam_prefixes:
            if digits.startswith(prefix):
                risk_score += 20
                reasons.append(f"Matches known spam prefix: {prefix}")
                break
        
        # Check for virtual number patterns
        virtual_patterns = ['1234', '1111', '2222', '3333', '4444', '5555', 
                           '6666', '7777', '8888', '9999', '0000']
        if any(pattern in digits for pattern in virtual_patterns):
            risk_score += 15
            reasons.append("Virtual number pattern detected")
        
        # Very simple heuristic - in reality, you'd use a database or API
        if risk_score == 0:
            risk_score = 10  # Default low risk
        
        return {
            'risk_score': min(100, risk_score),
            'risk_level': self._get_risk_level(risk_score),
            'reasons': reasons,
            'description': self._get_risk_description(risk_score)
        }
    
    def _get_risk_level(self, score):
        if score < 20:
            return "Low"
        elif score < 50:
            return "Medium"
        else:
            return "High"
    
    def _get_risk_description(self, score):
        if score < 20:
            return "This number appears to be low risk."
        elif score < 50:
            return "This number shows some risk factors. Exercise caution."
        else:
            return "This number appears to be high risk. Avoid if possible."

# Web search module
class WebSearchModule(InvestigationModule):
    def __init__(self):
        super().__init__("web_search")
        self.headers = {
            'User-Agent': app.config['USER_AGENT']
        }
    
    def _execute(self, phone_number):
        # Simulated web search
        return {
            'results': [],
            'message': 'Web search requires proper implementation with search APIs'
        }

# Module manager
class ModuleManager:
    def __init__(self):
        self.modules = {
            "phone_info": PhoneNumberModule(),
            "social_media": SocialMediaModule(),
            "spam_risk": SpamRiskModule(),
            "web_search": WebSearchModule()
        }
        self.ai_engine = AIReasoningEngine()
    
    def get_module(self, name):
        return self.modules.get(name)
    
    def execute_module(self, module_name, phone_number):
        module = self.get_module(module_name)
        if module:
            return module.execute(phone_number)
        raise ValueError(f"Module {module_name} not found")
    
    def execute_all(self, phone_number):
        results = {}
        for name, module in self.modules.items():
            try:
                results[name] = module.execute(phone_number)
            except Exception as e:
                results[name] = {"error": str(e)}
        
        # Add AI analysis
        results['ai_analysis'] = self.ai_engine.analyze({"phone_number": phone_number})
        
        return results

module_manager = ModuleManager()

# Results storage
results_cache = Cache()

# Routes
@app.route("/", methods=["POST", "GET"])
def index():
    if request.method == "GET":
        return render_template("index.html")
    
    if request.method == "POST":
        command = request.form["in"].strip().lower()
        
        if command == "help":
            return render_template("help.html")
        
        elif command.startswith("add phonenumber"):
            match = re.search(r"\d+", command)
            if match:
                phone_number = "+" + match.group(0)
                session['phone_number'] = phone_number
                session['enabled_features'] = []
                return render_template("phoneNumberSuccess.html", phone_number=phone_number)
            else:
                return render_template("failed.html", message="Invalid phone number format")
        
        elif command.startswith("add feature findowner"):
            session['enabled_features'] = session.get('enabled_features', []) + ['find_owner']
            return render_template("findOwnerSuccess.html", phone_number=session.get('phone_number'))
        
        elif command.startswith("add feature socialmedia"):
            session['enabled_features'] = session.get('enabled_features', []) + ['social_media']
            return render_template("socialMediaSuccess.html", phone_number=session.get('phone_number'))
        
        elif command.startswith("add feature spamrisk"):
            session['enabled_features'] = session.get('enabled_features', []) + ['spam_risk']
            return render_template("SpamRiskSuccess.html", phone_number=session.get('phone_number'))
        
        elif command.startswith("add feature getlinks"):
            session['enabled_features'] = session.get('enabled_features', []) + ['get_links']
            return render_template("GetLinksSuccess.html", phone_number=session.get('phone_number'))
        
        elif command.startswith("add feature getcomments"):
            session['enabled_features'] = session.get('enabled_features', []) + ['get_comments']
            return render_template("GetCommentsSuccess.html", phone_number=session.get('phone_number'))
        
        elif command == "show options":
            return render_template("showoptions.html", 
                phone_number=session.get('phone_number', 'Not Provided'),
                social_media='social_media' in session.get('enabled_features', []),
                get_links='get_links' in session.get('enabled_features', []),
                spam_risk='spam_risk' in session.get('enabled_features', []),
                find_owner='find_owner' in session.get('enabled_features', []),
                get_comments='get_comments' in session.get('enabled_features', [])
            )
        
        elif command.startswith("add feature *"):
            session['enabled_features'] = ['social_media', 'get_links', 'spam_risk', 'get_comments', 'find_owner']
            return render_template("featureAll.html", phone_number=session.get('phone_number'))
        
        elif command == "run":
            if 'phone_number' not in session:
                return render_template("failed.html", message="Phone number not provided")
            
            phone_number = session['phone_number']
            
            # Start investigation in background
            threading.Thread(target=run_investigation, args=(phone_number,)).start()
            time.sleep(2)
            return redirect(url_for("investigation"))
        
        elif command == "stats":
            return render_template("stats.html", stats=telemetry.get_stats())
        
        else:
            return render_template("unkownCommand.html")

@app.route("/investigation", methods=["GET"])
@phone_number_required
@rate_limit
def investigation():
    phone_number = session['phone_number']
    results = results_cache.get(phone_number)
    
    if not results:
        return render_template("investigation_in_progress.html", phone_number=phone_number)
    
    return render_template("result.html", phone_number=phone_number, **results)

@app.route("/investigation/status", methods=["GET"])
@phone_number_required
def investigation_status():
    phone_number = session['phone_number']
    results = results_cache.get(phone_number)
    
    if results:
        return jsonify({"status": "complete", "results": results})
    else:
        return jsonify({"status": "in_progress"})

@app.route("/investigationErr", methods=["GET"])
def investigationErr():
    return render_template("resultErr.html", phone_number=session.get('phone_number'))

def run_investigation(phone_number):
    """Run all enabled investigation features"""
    try:
        results = module_manager.execute_all(phone_number)
        results_cache.set(phone_number, results)
    except Exception as e:
        logger.error(f"Investigation failed for {phone_number}: {str(e)}")
        results_cache.set(phone_number, {"error": str(e)})

if __name__ == "__main__":
    # Create modules directory if it doesn't exist
    if not os.path.exists(app.config['MODULES_DIR']):
        os.makedirs(app.config['MODULES_DIR'])
    
    app.run(debug=True, host='0.0.0.0', port=5000)
