app.py (Complete)
"""
Phone Investigation System - Main application module.

This module contains the Flask application factory and core functionality
for the phone investigation system including routes, database models,
and business logic.
"""
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime


# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()


class User(UserMixin, db.Model):
    """
    User model for authentication and authorization.
    
    Attributes:
        id: Primary key
        username: Unique username for login
        email: User email address
        password_hash: Hashed password
        role: User role (admin, investigator, viewer)
        created_at: Account creation timestamp
    """
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='viewer')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        """Hash and set user password."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify user password."""
        return check_password_hash(self.password_hash, password)


class PhoneRecord(db.Model):
    """
    Phone record model for storing investigation data.
    
    Attributes:
        id: Primary key
        phone_number: Phone number being investigated
        owner_name: Name of phone owner
        address: Physical address
        carrier: Phone carrier/provider
        notes: Investigation notes
        created_by: ID of user who created record
        created_at: Record creation timestamp
        updated_at: Last update timestamp
    """
    __tablename__ = 'phone_records'
    
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), nullable=False, index=True)
    owner_name = db.Column(db.String(100))
    address = db.Column(db.Text)
    carrier = db.Column(db.String(50))
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    creator = db.relationship('User', backref='records')


@login_manager.user_loader
def load_user(user_id):
    """
    Load user by ID for Flask-Login.
    
    Args:
        user_id: User ID to load
        
    Returns:
        User object or None
    """
    return User.query.get(int(user_id))


def create_app(config=None):
    """
    Create and configure the Phone Investigation System Flask application.
    
    This factory function initializes the Flask app with all necessary
    configurations, extensions, and routes.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Flask: Configured Flask application instance
    """
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', 
        'sqlite:///phone_investigation.db'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Apply custom config if provided
    if config:
        app.config.update(config)
    
    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    # Routes
    @app.route('/')
    def index():
        """Home page route."""
        return render_template('index.html')
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """
        User login route.
        
        GET: Display login form
        POST: Process login credentials
        """
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            
            user = User.query.filter_by(username=username).first()
            
            if user and user.check_password(password):
                login_user(user)
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
            
            flash('Invalid username or password', 'error')
        
        return render_template('login.html')
    
    @app.route('/logout')
    @login_required
    def logout():
        """User logout route."""
        logout_user()
        flash('You have been logged out.', 'info')
        return redirect(url_for('index'))
    
    @app.route('/dashboard')
    @login_required
    def dashboard():
        """Main dashboard route for logged-in users."""
        records = PhoneRecord.query.order_by(PhoneRecord.created_at.desc()).limit(10).all()
        return render_template('dashboard.html', records=records)
    
    @app.route('/records/search', methods=['GET'])
    @login_required
    def search_records():
        """
        Search phone records.
        
        Query parameters:
            q: Search query (phone number, name, etc.)
            
        Returns:
            JSON array of matching records
        """
        query = request.args.get('q', '')
        
        if not query:
            return jsonify([])
        
        records = PhoneRecord.query.filter(
            db.or_(
                PhoneRecord.phone_number.contains(query),
                PhoneRecord.owner_name.contains(query),
                PhoneRecord.carrier.contains(query)
            )
        ).limit(50).all()
        
        return jsonify([{
            'id': record.id,
            'phone_number': record.phone_number,
            'owner_name': record.owner_name,
            'carrier': record.carrier,
            'created_at': record.created_at.isoformat()
        } for record in records])
    
    @app.route('/records/add', methods=['GET', 'POST'])
    @login_required
    def add_record():
        """
        Add new phone record.
        
        GET: Display add record form
        POST: Create new record
        """
        if request.method == 'POST':
            phone_number = request.form.get('phone_number')
            owner_name = request.form.get('owner_name')
            address = request.form.get('address')
            carrier = request.form.get('carrier')
            notes = request.form.get('notes')
            
            if not phone_number:
                flash('Phone number is required', 'error')
                return render_template('add_record.html')
            
            record = PhoneRecord(
                phone_number=phone_number,
                owner_name=owner_name,
                address=address,
                carrier=carrier,
                notes=notes,
                created_by=current_user.id
            )
            
            db.session.add(record)
            db.session.commit()
            
            flash('Record added successfully!', 'success')
            return redirect(url_for('dashboard'))
        
        return render_template('add_record.html')
    
    @app.route('/api/health')
    def health_check():
        """
        Health check endpoint for monitoring.
        
        Returns:
            JSON response with status and timestamp
        """
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'Phone Investigation System'
        })
    
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors."""
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors."""
        db.session.rollback()
        return render_template('500.html'), 500
    
    return app


if __name__ == '__main__':
    application = create_app()
    application.run(debug=True)
