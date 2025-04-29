from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import pandas as pd
import os
import random
from forex_python.converter import CurrencyRates
from db_manager import DatabaseManager
from models import User
import string
import time
from urllib.parse import urlparse
import json
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError
import uuid
from functools import wraps
from forms import AdminLoginForm

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize database manager
db = DatabaseManager()
c = CurrencyRates()

# Exchange rate configuration
EXCHANGE_RATE_CACHE_FILE = 'data/exchange_rate_cache.json'
EXCHANGE_RATE_CACHE_DURATION = 3600  # 1 hour in seconds
FALLBACK_RATE = 30.0  # Initial fallback rate
FALLBACK_RATE_UPDATE_INTERVAL = 86400  # 24 hours in seconds
API_TIMEOUT = 5  # seconds

# Credit card configuration
CARD_ISSUANCE_FEE = 1.0  # USD
CARD_EXPIRY_YEARS = 3

class CreditCard:
    def __init__(self, card_number, expiry_date, cvv, user_id, amount, status="pending"):
        self.card_number = card_number
        self.expiry_date = expiry_date
        self.cvv = cvv
        self.user_id = user_id
        self.amount = amount
        self.status = status
        self.created_at = datetime.now()
        self.approved_at = None

def get_exchange_rate():
    """Get USD to EGP exchange rate with caching, retry, and fallback mechanism"""
    # Try to get cached rate first
    cached_rate = _get_cached_rate()
    if cached_rate is not None:
        return cached_rate
    
    # If no valid cache, try to get fresh rate
    max_retries = 3
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            # Set timeout for the API call
            rate = c.convert('USD', 'EGP', 1, timeout=API_TIMEOUT)
            print(f"Successfully got exchange rate: {rate}")
            
            # Cache the successful rate
            _cache_rate(rate)
            return rate
            
        except Timeout:
            print(f"Attempt {attempt + 1} failed: API request timed out after {API_TIMEOUT} seconds")
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
            else:
                print("All attempts timed out, using fallback rate")
                return _get_fallback_rate()
                
        except ConnectionError:
            print(f"Attempt {attempt + 1} failed: Could not connect to forex API")
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
            else:
                print("All connection attempts failed, using fallback rate")
                return _get_fallback_rate()
                
        except RequestException as e:
            print(f"Attempt {attempt + 1} failed: API request error - {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
            else:
                print("All API requests failed, using fallback rate")
                return _get_fallback_rate()
                
        except Exception as e:
            print(f"Attempt {attempt + 1} failed with unexpected error: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
            else:
                print("All attempts failed with unexpected errors, using fallback rate")
                return _get_fallback_rate()

def _get_cached_rate():
    """Get cached exchange rate if it exists and is not expired"""
    try:
        if not os.path.exists(EXCHANGE_RATE_CACHE_FILE):
            return None
            
        with open(EXCHANGE_RATE_CACHE_FILE, 'r') as f:
            cache_data = json.load(f)
            
        cache_time = datetime.fromisoformat(cache_data['timestamp'])
        if datetime.now() - cache_time < timedelta(seconds=EXCHANGE_RATE_CACHE_DURATION):
            return cache_data['rate']
            
    except Exception as e:
        print(f"Error reading cache: {e}")
        
    return None

def _cache_rate(rate):
    """Cache the exchange rate with timestamp"""
    try:
        cache_data = {
            'rate': rate,
            'timestamp': datetime.now().isoformat()
        }
        
        os.makedirs(os.path.dirname(EXCHANGE_RATE_CACHE_FILE), exist_ok=True)
        with open(EXCHANGE_RATE_CACHE_FILE, 'w') as f:
            json.dump(cache_data, f)
            
    except Exception as e:
        print(f"Error caching rate: {e}")

def _get_fallback_rate():
    """Get fallback rate, updating it periodically"""
    try:
        if not os.path.exists(EXCHANGE_RATE_CACHE_FILE):
            return FALLBACK_RATE
            
        with open(EXCHANGE_RATE_CACHE_FILE, 'r') as f:
            cache_data = json.load(f)
            
        fallback_time = datetime.fromisoformat(cache_data.get('fallback_timestamp', '1970-01-01'))
        if datetime.now() - fallback_time > timedelta(seconds=FALLBACK_RATE_UPDATE_INTERVAL):
            # Try to get a fresh rate for fallback with timeout
            try:
                rate = c.convert('USD', 'EGP', 1, timeout=API_TIMEOUT)
                _update_fallback_rate(rate)
                return rate
            except Exception as e:
                print(f"Failed to update fallback rate: {str(e)}")
                # Continue with existing fallback rate
                
        return cache_data.get('fallback_rate', FALLBACK_RATE)
        
    except Exception as e:
        print(f"Error getting fallback rate: {str(e)}")
        return FALLBACK_RATE

def _update_fallback_rate(rate):
    """Update the fallback rate in cache"""
    try:
        cache_data = {}
        if os.path.exists(EXCHANGE_RATE_CACHE_FILE):
            with open(EXCHANGE_RATE_CACHE_FILE, 'r') as f:
                cache_data = json.load(f)
                
        cache_data['fallback_rate'] = rate
        cache_data['fallback_timestamp'] = datetime.now().isoformat()
        
        with open(EXCHANGE_RATE_CACHE_FILE, 'w') as f:
            json.dump(cache_data, f)
            
    except Exception as e:
        print(f"Error updating fallback rate: {e}")

# Create default admin user if not exists
def create_default_admin():
    admin_username = "admin"
    admin_password = "admin123"  # Change this in production!
    admin_email = "admin@bank.com"
    
    if not db.get_user_by_username(admin_username):
        admin = User(
            id=1,
            username=admin_username,
            email=admin_email,
            password_hash=generate_password_hash(admin_password),
            is_admin=True
        )
        db.add_user(admin)
        print("Default admin user created")

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID"""
    return db.get_user_by_id(user_id)

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        # Check if username or email already exists
        if db.get_user_by_username(username):
            flash('Username already exists. Please choose another.', 'danger')
            return redirect(url_for('register'))
        if db.get_user_by_email(email):
            flash('Email already exists. Please use another email.', 'danger')
            return redirect(url_for('register'))
        
        # Create new user with hashed password
        user = User(
            id=None,  # Will be set by database
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            balance=0.0,
            is_admin=False
        )
        
        if db.add_user(user):
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Registration failed. Please try again.', 'danger')
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Try to get user from database
        user = db.get_user_by_username(username)
        
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            if not next_page or urlparse(next_page).netloc != '':
                next_page = url_for('dashboard')
            return redirect(next_page)
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Get user's balance in USD
    balance_usd = db.get_balance(current_user.username)
    
    # Try to get EGP equivalent with fallback
    try:
        exchange_rate = get_exchange_rate()
        egp_balance = balance_usd * exchange_rate
    except Exception as e:
        print(f"Error converting currency: {e}")
        egp_balance = balance_usd * FALLBACK_RATE
    
    # Get recent transactions
    transactions = db.get_user_transactions(current_user.username)
    
    return render_template('dashboard.html', 
                         balance_usd=balance_usd,
                         egp_balance=egp_balance,
                         transactions=transactions)

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        new_username = request.form.get('username')
        if new_username and new_username != current_user.username:
            success = db.update_username(current_user.username, new_username)
            if success:
                flash('Username updated successfully!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Username already taken.', 'error')
    
    return render_template('settings.html')

@app.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    if request.method == 'POST':
        recipient_username = request.form.get('recipient_username')
        amount_str = request.form.get('amount')
        
        # Validate recipient username
        if not recipient_username:
            flash('Please enter recipient username.', 'error')
            return redirect(url_for('transfer'))
        
        # Add @ABM.Bank if not present
        if '@' not in recipient_username:
            recipient_username = f"{recipient_username}@ABM.Bank"
        
        # Check if recipient exists
        recipient = db.get_user_by_username(recipient_username)
        if not recipient:
            flash('Recipient not found.', 'error')
            return redirect(url_for('transfer'))
        
        # Validate amount
        try:
            amount_usd = float(amount_str)
            if amount_usd <= 0:
                flash('Amount must be greater than 0.', 'error')
                return redirect(url_for('transfer'))
        except (ValueError, TypeError):
            flash('Invalid amount. Please enter a valid number.', 'error')
            return redirect(url_for('transfer'))
        
        # Prevent self-transfer
        if recipient_username == f"{current_user.username}@ABM.Bank":
            flash('Cannot transfer to your own account.', 'error')
            return redirect(url_for('transfer'))
        
        # Check if sender has sufficient balance
        sender_balance = db.get_balance(current_user.username)
        if sender_balance < amount_usd:
            flash(f'Insufficient balance. Your balance: ${sender_balance:.2f}', 'error')
            return redirect(url_for('transfer'))
        
        # Process transfer
        success = db.process_transfer(current_user.username, recipient_username, amount_usd)
        
        if success:
            flash(f'Transfer of ${amount_usd:.2f} to {recipient_username} successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Transfer failed. Please try again.', 'error')
            return redirect(url_for('transfer'))
    
    return render_template('transfer.html')

def generate_credit_card():
    """Generate a new credit card with random number and CVV"""
    # Generate 16-digit card number (Visa format)
    card_number = '4' + ''.join(random.choices(string.digits, k=15))
    
    # Generate expiry date (3 years from now)
    expiry_date = (datetime.now() + timedelta(days=365*CARD_EXPIRY_YEARS)).strftime('%m/%y')
    
    # Generate 3-digit CVV
    cvv = ''.join(random.choices(string.digits, k=3))
    
    return card_number, expiry_date, cvv

@app.route('/request_card', methods=['GET', 'POST'])
@login_required
def request_card():
    if request.method == 'POST':
        try:
            amount = float(request.form.get('amount', 0))
            if amount <= 0:
                flash('Amount must be greater than 0', 'danger')
                return redirect(url_for('request_card'))
                
            # Check if user has enough balance for card issuance fee
            if db.get_balance(current_user.username) < CARD_ISSUANCE_FEE:
                flash('Insufficient balance for card issuance fee', 'danger')
                return redirect(url_for('request_card'))
            
            # Generate card details
            card_number, expiry_date, cvv = generate_credit_card()
            
            # Create card request
            card = CreditCard(
                card_number=card_number,
                expiry_date=expiry_date,
                cvv=cvv,
                user_id=current_user.username,
                amount=amount
            )
            
            # Save card request
            if db.create_card_request(card):
                # Deduct issuance fee
                db.process_transfer(
                    current_user.username,
                    'bank_fees',
                    CARD_ISSUANCE_FEE,
                    f'Card issuance fee for card ending in {card_number[-4:]}'
                )
                flash('Card request submitted successfully!', 'success')
                return redirect(url_for('my_cards'))
            else:
                flash('Failed to create card request', 'danger')
                
        except ValueError:
            flash('Invalid amount', 'danger')
            
        return redirect(url_for('request_card'))
        
    return render_template('request_card.html', 
                         CARD_ISSUANCE_FEE=CARD_ISSUANCE_FEE,
                         current_user=current_user)

@app.route('/my_cards')
@login_required
def my_cards():
    cards = db.get_user_cards(current_user.username)
    return render_template('my_cards.html', cards=cards)

@app.route('/admin/card_requests')
@login_required
def admin_card_requests():
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
        
    requests = db.get_pending_card_requests()
    return render_template('admin/card_requests.html', requests=requests)

@app.route('/admin/approve_card/<card_id>', methods=['POST'])
@login_required
def approve_card(card_id):
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
        
    try:
        card_number = request.form.get('card_number')
        expiry_date = request.form.get('expiry_date')
        cvv = request.form.get('cvv')
        validity_months = int(request.form.get('validity_months', 36))
        
        # Validate card details
        if not (len(card_number) == 16 and card_number.isdigit()):
            flash('Invalid card number', 'error')
            return redirect(url_for('admin_card_requests'))
            
        if not (len(cvv) == 3 and cvv.isdigit()):
            flash('Invalid CVV', 'error')
            return redirect(url_for('admin_card_requests'))
            
        if db.approve_card_request(card_id, card_number, expiry_date, cvv, validity_months):
            flash('Card request approved successfully', 'success')
        else:
            flash('Failed to approve card request', 'error')
            
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        
    return redirect(url_for('admin_card_requests'))

@app.route('/admin/reject_card/<card_id>', methods=['POST'])
@login_required
def reject_card(card_id):
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
        
    if db.reject_card_request(card_id):
        flash('Card request rejected', 'success')
    else:
        flash('Failed to reject card request', 'error')
        
    return redirect(url_for('admin_card_requests'))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You need admin privileges to access this page.', 'danger')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    total_users = len(db.get_all_users())
    pending_cards = db.get_pending_card_requests()
    return render_template('admin/dashboard.html', 
                         total_users=total_users,
                         pending_cards=pending_cards)

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = db.get_all_users()
    return render_template('admin/users.html', users=users)

@app.route('/admin/edit_user/<username>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(username):
    if request.method == 'POST':
        try:
            amount = float(request.form.get('amount', 0))
            note = request.form.get('note', '')
            
            if amount != 0:
                if db.add_balance(username, amount):
                    # Record the transaction
                    db.process_transfer(
                        'bank_admin',
                        username,
                        amount,
                        f'Admin balance adjustment: {note}'
                    )
                    flash(f'Updated balance for {username}', 'success')
                else:
                    flash('Failed to update balance', 'error')
            else:
                flash('No changes made', 'info')
                
        except ValueError:
            flash('Invalid amount', 'error')
            
        return redirect(url_for('edit_user', username=username))
        
    user = db.get_user_by_username(username)
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('admin_users'))
        
    transactions = db.get_user_transactions(username)
    return render_template('admin/edit_user.html', user=user, transactions=transactions)

@app.route('/admin/add_balance', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_add_balance():
    if request.method == 'POST':
        username = request.form.get('username')
        amount_str = request.form.get('amount')
        reason = request.form.get('reason', '')
        
        # Validate username
        if not username:
            flash('Please enter a username', 'danger')
            return redirect(url_for('admin_add_balance'))
            
        # Check if user exists
        user = db.get_user_by_username(username)
        if not user:
            flash('User not found', 'danger')
            return redirect(url_for('admin_add_balance'))
            
        # Validate amount
        try:
            amount = float(amount_str)
            if amount <= 0:
                flash('Amount must be greater than 0', 'danger')
                return redirect(url_for('admin_add_balance'))
        except (ValueError, TypeError):
            flash('Invalid amount. Please enter a valid number.', 'danger')
            return redirect(url_for('admin_add_balance'))
            
        # Add balance
        if db.add_balance(username, amount):
            # Record the transaction
            db.process_transfer(
                'bank_admin',
                username,
                amount,
                f'Admin balance addition: {reason}'
            )
            flash(f'Successfully added ${amount:.2f} to {username}\'s account', 'success')
            return redirect(url_for('admin_users'))
        else:
            flash('Failed to add balance. Please try again.', 'danger')
            
    # Get list of users for the form
    users = db.get_all_users()
    return render_template('admin/add_balance.html', users=users)

@app.route('/invest', methods=['GET', 'POST'])
@login_required
def invest():
    if request.method == 'POST':
        amount_usd = float(request.form.get('amount'))
        period = int(request.form.get('period'))  # in months
        
        if db.create_investment(current_user.username, amount_usd, period):
            flash('Investment created successfully!')
        else:
            flash('Investment failed. Please check your balance.')
        
        return redirect(url_for('dashboard'))
    
    return render_template('invest.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated and current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    form = AdminLoginForm()
    if form.validate_on_submit():
        user = db.get_user_by_username(form.username.data)
        if user and user.is_admin and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            if not next_page or urlparse(next_page).netloc != '':
                next_page = url_for('admin_dashboard')
            flash('Welcome back, Admin!', 'success')
            return redirect(next_page)
        flash('Invalid username or password', 'danger')
    return render_template('admin_login.html', form=form)

@app.route('/admin/logout')
@login_required
@admin_required
def admin_logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('admin_login'))

# Call this function when the app starts
create_default_admin()

if __name__ == '__main__':
    app.run(debug=True) 