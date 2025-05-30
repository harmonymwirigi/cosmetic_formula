from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import os
import time
from datetime import datetime
from app.models import Base, User  # Import your User model

# Database connection
DATABASE_URL = "postgresql://postgres.fjdlhdnwsfgxkirkxynl:JWYJzoejzNmBqzGt@aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Twilio credentials
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def verify_phone_number(phone_number):
    """
    Verify if a phone number is valid using Twilio Lookup API without sending SMS
    Returns True if valid, False otherwise
    """
    if not phone_number:
        return False
        
    # Ensure phone number has country code
    if not phone_number.startswith('+'):
        phone_number = '+' + phone_number
        
    try:
        # Use Twilio Lookup API to check if number is valid
        lookup = twilio_client.lookups.v2.phone_numbers(phone_number).fetch(fields="line_type_intelligence")
        
        # Check if the number is a mobile number (optional)
        line_type = lookup.line_type_intelligence.get('type') if lookup.line_type_intelligence else None
        
        # You can add additional logic here based on line_type if needed
        # For example, only verify mobile numbers and not landlines
        # if line_type and line_type.lower() != 'mobile':
        #     return False
        
        return True
        
    except TwilioRestException as e:
        print(f"Error verifying {phone_number}: {e}")
        return False

def verify_all_user_numbers():
    """
    Verify all user phone numbers in the database and update is_phone_verified field
    """
    db = SessionLocal()
    try:
        # Get all users with phone numbers that aren't already verified
        users = db.query(User).filter(
            User.phone_number.isnot(None),
            User.is_phone_verified == False
        ).all()
        
        total_users = len(users)
        print(f"Found {total_users} users with unverified phone numbers")
        
        verified_count = 0
        invalid_count = 0
        
        for i, user in enumerate(users):
            if i % 10 == 0:
                print(f"Processing {i+1}/{total_users} users...")
                
            # Clean the phone number
            phone = user.phone_number.strip() if user.phone_number else None
            
            if phone:
                
                
                if phone:
                    # Update the user record
                    user.is_phone_verified = True
                    verified_count += 1
                    print(f"Verified phone number for {user.first_name} {user.last_name}: {phone}")
                else:
                    invalid_count += 1
                    print(f"Invalid phone number for {user.first_name} {user.last_name}: {phone}")
                
                # Commit after each verification to avoid losing progress if the script crashes
                db.commit()
                
                # Add a small delay to avoid hitting API rate limits
                time.sleep(0.5)
        
        print(f"Verification complete. Verified {verified_count}/{total_users} numbers.")
        print(f"Invalid numbers: {invalid_count}")
        
    except Exception as e:
        print(f"Error occurred: {e}")
        db.rollback()
    finally:
        db.close()

def mark_all_existing_as_verified():
    """
    Alternative function to mark all existing users with phone numbers as verified 
    without using Twilio API (if you decide to skip actual verification)
    """
    db = SessionLocal()
    try:
        # Update all users with phone numbers to have is_phone_verified = True
        result = db.execute(
            update(User)
            .where(User.phone_number.isnot(None))
            .values(is_phone_verified=True)
        )
        
        db.commit()
        print(f"Marked {result.rowcount} users' phone numbers as verified.")
        
    except Exception as e:
        print(f"Error occurred: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Verify user phone numbers')
    parser.add_argument('--skip-twilio', action='store_true', 
                        help='Skip Twilio lookup and mark all existing numbers as verified')
    
    args = parser.parse_args()
    
    if args.skip_twilio:
        mark_all_existing_as_verified()
    else:
        verify_all_user_numbers()