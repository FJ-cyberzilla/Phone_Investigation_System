from app import create_app
from app.ai.analyzer import AIAnalyzer

app = create_app()

# Initialize AI analyzer
app.ai_analyzer = AIAnalyzer()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
