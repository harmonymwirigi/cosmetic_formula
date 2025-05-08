# backend/share_notion_db.py

import os
import asyncio
import webbrowser
from dotenv import load_dotenv
import httpx

load_dotenv()

async def share_notion_databases():
    # Get integration info
    api_key = os.getenv("NOTION_API_KEY")
    integration_name = input("Enter the name of your Notion integration (e.g., 'Cosmetic Formula Lab'): ")
    
    # Get database URLs
    formula_db_url = input("Enter the URL of your Formula Database: ")
    docs_db_url = input("Enter the URL of your Documentation Database: ")
    
    # Extract database IDs from URLs
    formula_db_id = formula_db_url.split("?")[0].split("/")[-1]
    docs_db_id = docs_db_url.split("?")[0].split("/")[-1]
    
    print("\nTo share your databases with the integration:")
    print(f"1. For Formula Database (ID: {formula_db_id}):")
    print("   - Click 'Share' in the top-right corner")
    print(f"   - Search for '{integration_name}' and add it with 'Full access'")
    
    print(f"\n2. For Documentation Database (ID: {docs_db_id}):")
    print("   - Click 'Share' in the top-right corner")
    print(f"   - Search for '{integration_name}' and add it with 'Full access'")
    
    # Offer to open the databases in the browser
    should_open = input("\nWould you like to open these databases in your browser now? (y/n): ")
    if should_open.lower() == 'y':
        webbrowser.open(formula_db_url)
        webbrowser.open(docs_db_url)
    
    print("\nAfter sharing, update your .env file with these values:")
    print(f"NOTION_FORMULAS_DB_ID={formula_db_id}")
    print(f"NOTION_DOCS_DB_ID={docs_db_id}")
    print("\nThen run the direct_notion_test.py script to verify access.")

if __name__ == "__main__":
    asyncio.run(share_notion_databases())