from app import create_app
from app.ai.analyzer import AIAnalyzer

"""
Main entry point for running the Phone Investigation System application.
This module starts the development server for the Flask application.
"""
from app import create_app

def main():
    """
    Initialize and run the Flask application.
    
    This function creates the app instance and starts the development server
    with debug mode enabled for development purposes.
    """
    application = create_app()
    application.run(host='0.0.0.0', port=5000)


if __name__ == '__main__':
    main()
