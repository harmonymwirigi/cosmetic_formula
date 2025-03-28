"""
Database migration script to add subscription fields to the users table.
Run this script after updating the models.py file.
"""
from sqlalchemy import create_engine, Column, Boolean, String, DateTime, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import enum
from app.config import settings
import alembic.migration
import alembic.operations

# Define the SubscriptionType enum
class SubscriptionType(str, enum.Enum):
    FREE = "free"
    PREMIUM = "premium"
    PROFESSIONAL = "professional"

# Create engine
engine = create_engine(settings.DATABASE_URL)

# Connect to the database
conn = engine.connect()

# Create an Alembic Operations object
ctx = alembic.migration.MigrationContext.configure(conn)
op = alembic.operations.Operations(ctx)

# Add the new columns to the users table
try:
    # Check if columns already exist
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    if 'subscription_type' not in columns:
        op.add_column('users', Column('subscription_type', 
                                      Enum(SubscriptionType, name='subscriptiontype'), 
                                      server_default='free'))
    
    if 'needs_subscription' not in columns:
        op.add_column('users', Column('needs_subscription', Boolean, 
                                      server_default='true'))
    
    if 'subscription_id' not in columns:
        op.add_column('users', Column('subscription_id', String))
    
    if 'subscription_expires_at' not in columns:
        op.add_column('users', Column('subscription_expires_at', DateTime(timezone=True)))
    
    print("Migration successful! Added subscription columns to users table.")
except Exception as e:
    print(f"Error during migration: {e}")
    # Rollback if needed
    conn.rollback()
finally:
    conn.close()
    engine.dispose()

print("To apply these changes to all existing users, you may want to run:")
print("UPDATE users SET needs_subscription = TRUE WHERE subscription_type IS NULL OR subscription_type = 'free';")