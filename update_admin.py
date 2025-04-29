from db_manager import DatabaseManager

def update_admin_balance():
    db = DatabaseManager()
    
    # Add balance to admin account
    admin_username = "admin@ABM.Bank"  # Updated username
    success = db.add_balance(admin_username, 1000.0)
    
    if success:
        # Record the transaction
        db.process_transfer(
            'bank_admin',
            admin_username,
            1000.0,
            'Initial admin balance'
        )
        print("Successfully added $1000.00 to admin account")
    else:
        print("Failed to add balance")

if __name__ == '__main__':
    update_admin_balance() 