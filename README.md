# Digital Bank Application

A modern digital banking application built with Flask that provides essential banking features including money transfers, investments, and virtual debit cards.

## Features

- User registration and authentication
- Account balance management in EGP with USD conversion
- Money transfers between users
- Investment options with 2% monthly interest
- Virtual debit card requests and management
- Admin dashboard for card request approvals
- Excel-based data storage
- Real-time currency conversion

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd digital-bank
```

2. Create a virtual environment:
```bash
python -m venv venv
```

3. Activate the virtual environment:
- Windows:
```bash
venv\Scripts\activate
```
- Unix/MacOS:
```bash
source venv/bin/activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Application

1. Make sure your virtual environment is activated

2. Run the Flask application:
```bash
python app.py
```

3. Open your web browser and navigate to:
```
http://localhost:5000
```

## Usage

1. Register a new account using your email address
2. Log in to access your dashboard
3. View your balance in EGP and USD
4. Send money to other users using their account numbers
5. Create investments with different time periods
6. Request virtual debit cards
7. Admin users can approve card requests through the admin dashboard

## File Structure

```
digital-bank/
├── app.py              # Main application file
├── db_manager.py       # Database management class
├── models.py           # User model
├── requirements.txt    # Project dependencies
├── README.md          # This file
├── database/          # Excel database files
└── templates/         # HTML templates
    ├── base.html
    ├── index.html
    ├── login.html
    ├── register.html
    ├── dashboard.html
    ├── transfer.html
    ├── invest.html
    ├── request_card.html
    └── admin/
        └── dashboard.html
```

## Security Notes

- All passwords are hashed before storage
- Session management is handled securely by Flask-Login
- Excel files are used for data storage in this demo version
- For production use, consider using a proper database system

## Contributing

1. Fork the repository
2. Create a new branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License. 