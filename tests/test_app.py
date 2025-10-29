"""
Test suite for Phone Investigation System.

This module contains unit tests for the application routes and functionality.
"""
import pytest
from app import create_app, db, User


@pytest.fixture
def app():
    """Create and configure a test app instance."""
    test_app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False
    })
    
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create a test client for the app."""
    return app.test_client()


def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get('/api/health')
    assert response.status_code == 200
    assert b'healthy' in response.data


def test_index_page(client):
    """Test the index page loads."""
    response = client.get('/')
    assert response.status_code == 200
