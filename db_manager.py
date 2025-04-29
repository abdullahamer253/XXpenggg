import pandas as pd
import os
from datetime import datetime, timedelta
from models import User
import random
from forex_python.converter import CurrencyRates
import sqlite3

class DatabaseManager:
    def __init__(self):
        self.db_path = 'data/'
        self.users_file = 'data/users.xlsx'
        self.transactions_file = 'data/transactions.xlsx'
        self.cards_file = 'database/cards.xlsx'
        self.investments_file = 'data/investments.xlsx'
        self.conn = sqlite3.connect('database.db', check_same_thread=False)
        self._initialize_database()
        self._initialize_files()

    def _initialize_database(self):
        """Initialize the SQLite database with required tables"""
        try:
            cursor = self.conn.cursor()
            
            # Create users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    balance REAL DEFAULT 0.0,
                    is_admin BOOLEAN DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1
                )
            ''')
            
            # Create transactions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    amount REAL NOT NULL,
                    description TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create credit_cards table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS credit_cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_number TEXT NOT NULL,
                    expiry_date TEXT NOT NULL,
                    cvv TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    approved_at DATETIME
                )
            ''')
            
            self.conn.commit()
        except Exception as e:
            print(f"Error initializing database: {e}")

    def _initialize_files(self):
        """Initialize the database if it doesn't exist"""
        # Create data directory if it doesn't exist
        if not os.path.exists(self.db_path):
            os.makedirs(self.db_path)

        # Initialize users file if it doesn't exist
        try:
            pd.read_excel(self.users_file)
        except FileNotFoundError:
            df = pd.DataFrame(columns=['username', 'email', 'password_hash', 'balance_usd', 'account_number'])
            df.to_excel(self.users_file, index=False)

        # Initialize transactions file if it doesn't exist
        try:
            pd.read_excel(self.transactions_file)
        except FileNotFoundError:
            df = pd.DataFrame(columns=['user_id', 'type', 'amount_usd', 'timestamp', 'description'])
            df.to_excel(self.transactions_file, index=False)

        # Initialize investments file if it doesn't exist
        try:
            pd.read_excel(self.investments_file)
        except FileNotFoundError:
            df = pd.DataFrame(columns=['user_id', 'amount_usd', 'period_months', 'start_date', 'end_date', 'status'])
            df.to_excel(self.investments_file, index=False)

    def create_user(self, email, password_hash, name, username, account_number):
        """Create a new user"""
        try:
            df = pd.read_excel(self.users_file)
            
            # Check if email or username already exists
            if len(df[df['email'] == email]) > 0:
                print(f"Email already exists: {email}")
                return False
            if len(df[df['username'] == username]) > 0:
                print(f"Username already exists: {username}")
                return False
            
            new_id = len(df) + 1
            new_user = pd.DataFrame({
                'id': [new_id],
                'email': [email],
                'password_hash': [password_hash],
                'name': [name],
                'username': [username],
                'account_number': [account_number],
                'balance_usd': [0.0],
                'is_admin': [False]
            })
            
            df = pd.concat([df, new_user], ignore_index=True)
            df.to_excel(self.users_file, index=False)
            return True
        except Exception as e:
            print(f"Error creating user: {e}")
            return False

    def update_username(self, user_id, new_username):
        """Update user's username"""
        try:
            df = pd.read_excel(self.users_file)
            
            # Check if new username already exists
            if len(df[(df['username'] == new_username) & (df['id'] != user_id)]) > 0:
                print(f"Username already exists: {new_username}")
                return False
            
            df.loc[df['id'] == user_id, 'username'] = new_username
            df.to_excel(self.users_file, index=False)
            return True
        except Exception as e:
            print(f"Error updating username: {e}")
            return False

    def get_user_by_username(self, username):
        """Get user by username"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT id, username, email, password_hash, balance, is_admin
                FROM users
                WHERE username = ?
            ''', (username,))
            row = cursor.fetchone()
            if row:
                return User(
                    id=row[0],
                    username=row[1],
                    email=row[2],
                    password_hash=row[3],
                    balance=row[4],
                    is_admin=row[5]
                )
            return None
        except Exception as e:
            print(f"Error getting user by username: {e}")
            return None

    def get_user_by_email(self, email):
        """Get user by email"""
        try:
            df = pd.read_excel(self.users_file)
            user_data = df[df['email'] == email]
            if not user_data.empty:
                return User.from_dict(user_data.iloc[0].to_dict())
            return None
        except Exception as e:
            print(f"Error getting user by email: {e}")
            return None

    def get_user_by_id(self, user_id):
        """Get user by ID"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT id, username, email, password_hash, balance, is_admin
                FROM users
                WHERE id = ?
            ''', (user_id,))
            row = cursor.fetchone()
            if row:
                return User(
                    id=row[0],
                    username=row[1],
                    email=row[2],
                    password_hash=row[3],
                    balance=row[4],
                    is_admin=row[5]
                )
            return None
        except Exception as e:
            print(f"Error getting user by id: {e}")
            return None

    def get_balance(self, username):
        """Get user's balance in USD"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT balance FROM users
                WHERE username = ?
            ''', (username,))
            row = cursor.fetchone()
            if row:
                return float(row[0])
            return 0.0
        except Exception as e:
            print(f"Error getting balance: {e}")
            return 0.0

    def process_transfer(self, sender, recipient, amount, description=""):
        """Process a transfer and record the transaction"""
        try:
            cursor = self.conn.cursor()
            
            # Start transaction
            cursor.execute('BEGIN TRANSACTION')
            
            # Check if sender has sufficient balance
            cursor.execute('''
                SELECT balance FROM users WHERE username = ?
            ''', (sender,))
            sender_balance = cursor.fetchone()
            if not sender_balance or sender_balance[0] < amount:
                self.conn.rollback()
                return False
            
            # Update sender's balance
            cursor.execute('''
                UPDATE users 
                SET balance = balance - ?
                WHERE username = ?
            ''', (amount, sender))
            
            # Update recipient's balance
            cursor.execute('''
                UPDATE users 
                SET balance = balance + ?
                WHERE username = ?
            ''', (amount, recipient))
            
            # Record transaction
            cursor.execute('''
                INSERT INTO transactions 
                (sender, recipient, amount, description, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (sender, recipient, amount, description, datetime.now()))
            
            # Commit transaction
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error processing transfer: {e}")
            self.conn.rollback()
            return False

    def _record_transaction(self, sender_id, recipient_id, amount_usd):
        """Record a transaction"""
        try:
            df = pd.read_excel(self.transactions_file)
            users_df = pd.read_excel(self.users_file)
            
            # Get usernames
            sender_username = users_df[users_df['id'] == sender_id]['username'].iloc[0]
            recipient_username = users_df[users_df['id'] == recipient_id]['username'].iloc[0]
            
            new_transaction = pd.DataFrame({
                'id': [len(df) + 1],
                'sender_id': [sender_id],
                'recipient_id': [recipient_id],
                'sender_username': [sender_username],
                'recipient_username': [recipient_username],
                'amount_usd': [float(amount_usd)],
                'timestamp': [datetime.now()]
            })
            
            df = pd.concat([df, new_transaction], ignore_index=True)
            df.to_excel(self.transactions_file, index=False)
        except Exception as e:
            print(f"Error recording transaction: {e}")
            raise

    def get_transactions(self, user_id):
        """Get user's transactions"""
        df = pd.read_excel(self.transactions_file)
        return df[(df['sender_id'] == user_id) | (df['recipient_id'] == user_id)].to_dict('records')

    def create_card_request(self, card):
        """Create a new credit card request"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO credit_cards 
                (card_number, expiry_date, cvv, user_id, amount, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                card.card_number,
                card.expiry_date,
                card.cvv,
                card.user_id,
                card.amount,
                card.status,
                card.created_at
            ))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error creating card request: {e}")
            return False

    def get_user_cards(self, user_id):
        """Get all cards for a user"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT * FROM credit_cards 
                WHERE user_id = ? AND status = 'approved'
                ORDER BY created_at DESC
            ''', (user_id,))
            return cursor.fetchall()
        except Exception as e:
            print(f"Error getting user cards: {e}")
            return []

    def get_pending_card_requests(self):
        """Get all pending card requests"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT * FROM credit_cards 
                WHERE status = 'pending'
                ORDER BY created_at DESC
            ''')
            return cursor.fetchall()
        except Exception as e:
            print(f"Error getting pending card requests: {e}")
            return []

    def approve_card_request(self, card_id, card_number, expiry_date, cvv, validity_months):
        """Approve a card request with custom card details"""
        try:
            cursor = self.conn.cursor()
            
            # Calculate expiry date based on validity months
            expiry_date_obj = datetime.strptime(expiry_date, '%m/%y')
            new_expiry = (expiry_date_obj + timedelta(days=30*validity_months)).strftime('%m/%y')
            
            cursor.execute('''
                UPDATE credit_cards 
                SET status = 'approved', 
                    approved_at = ?,
                    card_number = ?,
                    expiry_date = ?,
                    cvv = ?
                WHERE id = ? AND status = 'pending'
            ''', (datetime.now(), card_number, new_expiry, cvv, card_id))
            
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error approving card request: {e}")
            return False

    def reject_card_request(self, card_id):
        """Reject a card request"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE credit_cards 
                SET status = 'rejected'
                WHERE id = ? AND status = 'pending'
            ''', (card_id,))
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error rejecting card request: {e}")
            return False

    def add_balance(self, username, amount):
        """Add balance to a user's account"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE users 
                SET balance = balance + ?
                WHERE username = ?
            ''', (amount, username))
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error adding balance: {e}")
            return False

    def get_user_transactions(self, username):
        """Get all transactions for a user"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT * FROM transactions 
                WHERE sender = ? OR recipient = ?
                ORDER BY timestamp DESC
                LIMIT 10
            ''', (username, username))
            return cursor.fetchall()
        except Exception as e:
            print(f"Error getting user transactions: {e}")
            return []

    def create_investment(self, user_id, amount_usd, period):
        """Create a new investment"""
        # Check if user has sufficient balance
        if self.get_balance(user_id) < amount_usd:
            return False
            
        # Deduct amount from user's balance
        df_users = pd.read_excel(self.users_file)
        df_users.loc[df_users['id'] == user_id, 'balance_usd'] -= amount_usd
        df_users.to_excel(self.users_file, index=False)
        
        # Create investment record
        df_investments = pd.read_excel(self.investments_file)
        start_date = datetime.now()
        
        new_investment = pd.DataFrame({
            'id': [len(df_investments) + 1],
            'user_id': [user_id],
            'amount_usd': [amount_usd],
            'start_date': [start_date],
            'end_date': [start_date.replace(month=start_date.month + period)],
            'interest_rate': [0.02]  # 2% monthly
        })
        
        df_investments = pd.concat([df_investments, new_investment], ignore_index=True)
        df_investments.to_excel(self.investments_file, index=False)
        return True

    def get_user_by_account_number(self, account_number):
        """Get user by account number"""
        try:
            df = pd.read_excel(self.users_file)
            user_data = df[df['account_number'] == account_number]
            
            if len(user_data) == 0:
                return None
                
            user_dict = user_data.iloc[0].to_dict()
            return User.from_dict(user_dict)
        except Exception as e:
            print(f"Error getting user by account number: {e}")
            return None

    def update_user_balance(self, username, new_balance):
        df = pd.read_excel(self.users_file)
        df.loc[df['username'] == username, 'balance_usd'] = new_balance
        df.to_excel(self.users_file, index=False)

    def add_transaction(self, user_id, transaction_type, amount_usd, description):
        df = pd.read_excel(self.transactions_file)
        new_row = {
            'user_id': user_id,
            'type': transaction_type,
            'amount_usd': amount_usd,
            'timestamp': pd.Timestamp.now(),
            'description': description
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        df.to_excel(self.transactions_file, index=False)

    def get_user_transactions(self, user_id):
        df = pd.read_excel(self.transactions_file)
        return df[df['user_id'] == user_id].to_dict('records')

    def add_investment(self, user_id, amount_usd, period_months):
        df = pd.read_excel(self.investments_file)
        start_date = pd.Timestamp.now()
        end_date = start_date + pd.DateOffset(months=period_months)
        new_row = {
            'user_id': user_id,
            'amount_usd': amount_usd,
            'period_months': period_months,
            'start_date': start_date,
            'end_date': end_date,
            'status': 'active'
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        df.to_excel(self.investments_file, index=False)

    def get_user_investments(self, user_id):
        df = pd.read_excel(self.investments_file)
        return df[df['user_id'] == user_id].to_dict('records')

    def add_user(self, user):
        """Add a new user to the database"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, balance, is_admin)
                VALUES (?, ?, ?, ?, ?)
            ''', (user.username, user.email, user.password_hash, user.balance, user.is_admin))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error adding user: {e}")
            return False

    def get_all_users(self):
        """Get all users"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT id, username, email, balance, is_admin, is_active
                FROM users
                ORDER BY username
            ''')
            return cursor.fetchall()
        except Exception as e:
            print(f"Error getting all users: {e}")
            return []

    def get_recent_admin_actions(self):
        """Get recent admin actions from transactions"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT timestamp, sender, amount, description
                FROM transactions
                WHERE sender = 'bank_admin'
                ORDER BY timestamp DESC
                LIMIT 10
            ''')
            
            actions = []
            for row in cursor.fetchall():
                actions.append({
                    'timestamp': row[0],
                    'action_type': 'Balance Adjustment',
                    'username': row[1],
                    'details': f"${row[2]:.2f} - {row[3]}"
                })
            return actions
        except Exception as e:
            print(f"Error getting recent admin actions: {e}")
            return [] 