# backend/seed_currencies.py - Run this AFTER your migration

from sqlalchemy.orm import Session
from app.database import engine, SessionLocal
from app.models import Currency

def seed_default_currencies():
    """Add default currencies to the database"""
    db = SessionLocal()
    
    try:
        # Check if currencies already exist
        existing_count = db.query(Currency).count()
        if existing_count > 0:
            print(f"Currencies already exist ({existing_count} found). Skipping seed.")
            return
        
        # Default currencies with approximate exchange rates
        default_currencies = [
            {'code': 'USD', 'name': 'US Dollar', 'symbol': '$', 'rate': 1.0},
            {'code': 'EUR', 'name': 'Euro', 'symbol': '€', 'rate': 0.85},
            {'code': 'GBP', 'name': 'British Pound', 'symbol': '£', 'rate': 0.73},
            {'code': 'CAD', 'name': 'Canadian Dollar', 'symbol': 'C$', 'rate': 1.35},
            {'code': 'AUD', 'name': 'Australian Dollar', 'symbol': 'A$', 'rate': 1.55},
            {'code': 'JPY', 'name': 'Japanese Yen', 'symbol': '¥', 'rate': 150.0},
            {'code': 'CHF', 'name': 'Swiss Franc', 'symbol': 'CHF', 'rate': 0.91},
            {'code': 'CNY', 'name': 'Chinese Yuan', 'symbol': '¥', 'rate': 7.25},
            {'code': 'INR', 'name': 'Indian Rupee', 'symbol': '₹', 'rate': 83.0},
            {'code': 'BRL', 'name': 'Brazilian Real', 'symbol': 'R$', 'rate': 5.2},
        ]
        
        for curr_data in default_currencies:
            currency = Currency(
                code=curr_data['code'],
                name=curr_data['name'],
                symbol=curr_data['symbol'],
                exchange_rate_to_usd=curr_data['rate'],
                is_active=True
            )
            db.add(currency)
        
        db.commit()
        print(f"Successfully added {len(default_currencies)} default currencies!")
        
        # Print the currencies for verification
        currencies = db.query(Currency).all()
        for curr in currencies:
            print(f"  {curr.code} - {curr.name} ({curr.symbol}) - Rate: {curr.exchange_rate_to_usd}")
            
    except Exception as e:
        print(f"Error seeding currencies: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("Seeding default currencies...")
    seed_default_currencies()
    print("Done!")