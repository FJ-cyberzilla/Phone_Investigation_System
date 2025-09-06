import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import joblib
import os
from app.core.config import MODELS_DIR

class AIAnalyzer:
    def __init__(self):
        self.models = {}
        self.scaler = StandardScaler()
        self.load_models()
    
    def load_models(self):
        """Load pre-trained ML models"""
        try:
            # Load risk assessment model
            risk_model_path = os.path.join(MODELS_DIR, 'risk_assessor.pkl')
            if os.path.exists(risk_model_path):
                self.models['risk'] = joblib.load(risk_model_path)
            
            # Load pattern detection model
            pattern_model_path = os.path.join(MODELS_DIR, 'pattern_detector.pkl')
            if os.path.exists(pattern_model_path):
                self.models['pattern'] = joblib.load(pattern_model_path)
                
        except Exception as e:
            print(f"Error loading models: {e}")
    
    def extract_features(self, investigation_data):
        """Extract features from investigation data for ML models"""
        features = []
        
        # Phone number features
        phone_features = self._extract_phone_features(investigation_data.get('phone_info', {}))
        features.extend(phone_features)
        
        # Social media features
        social_features = self._extract_social_features(investigation_data.get('social_media', {}))
        features.extend(social_features)
        
        # Risk features
        risk_features = self._extract_risk_features(investigation_data.get('spam_risk', {}))
        features.extend(risk_features)
        
        return np.array(features).reshape(1, -1)
    
    def analyze_risk(self, features):
        """Predict risk level using ML model"""
        if 'risk' not in self.models:
            return self._fallback_risk_analysis(features)
        
        try:
            prediction = self.models['risk'].predict(features)
            probability = self.models['risk'].predict_proba(features)
            return {
                'risk_level': prediction[0],
                'confidence': float(np.max(probability)),
                'factors': self._get_risk_factors(features)
            }
        except Exception as e:
            return self._fallback_risk_analysis(features)
    
    def _fallback_risk_analysis(self, features):
        """Fallback analysis if ML model is not available"""
        # Simple heuristic-based risk assessment
        risk_score = np.mean(features) * 100
        if risk_score < 30:
            risk_level = "low"
        elif risk_score < 70:
            risk_level = "medium"
        else:
            risk_level = "high"
        
        return {
            'risk_level': risk_level,
            'confidence': 0.7,
            'factors': ['heuristic_analysis']
        }
    
    def _extract_phone_features(self, phone_data):
        # Extract features from phone data
        features = []
        features.append(1 if phone_data.get('valid', False) else 0)
        features.append(len(phone_data.get('carrier', '')) / 50)  # Normalized
        return features
    
    def _extract_social_features(self, social_data):
        # Extract features from social media data
        features = []
        platforms = ['facebook', 'twitter', 'instagram', 'linkedin']
        for platform in platforms:
            features.append(1 if social_data.get(platform, {}).get('found', False) else 0)
        return features
    
    def _extract_risk_features(self, risk_data):
        # Extract features from risk data
        features = []
        features.append(risk_data.get('risk_score', 0) / 100)  # Normalized
        features.append(len(risk_data.get('reasons', [])) / 10)  # Normalized
        return features
    
    def _get_risk_factors(self, features):
        # Determine main risk factors based on feature importance
        factors = []
        if features[0][0] < 0.5:  # Phone validity
            factors.append('invalid_phone')
        if features[0][1] < 0.3:  # Carrier length
            factors.append('unknown_carrier')
        if features[0][4] > 0.7:  # Risk score
            factors.append('high_risk_score')
        return factors
