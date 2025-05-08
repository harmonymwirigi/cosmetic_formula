# backend/direct_notion_test.py

import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

async def test_notion_api():
    # Get API key and database ID
    api_key = os.getenv("NOTION_API_KEY")
    # Always remove hyphens from database IDs
    db_id = os.getenv("NOTION_FORMULAS_DB_ID", "").replace("-", "")
    
    print(f"Testing with API key: {api_key[:4]}...{api_key[-4:]} and database ID: {db_id}")
    
    # Setup headers
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    # 1. Test user access (verify API key works)
    print("\n1. Testing basic API access...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("https://api.notion.com/v1/users/me", headers=headers)
            if response.status_code == 200:
                print(f"✓ API key is valid. User: {response.json().get('name')}")
            else:
                print(f"✗ API key validation failed: {response.status_code}")
                print(f"  Response: {response.text}")
                return
        except Exception as e:
            print(f"✗ Error testing API key: {e}")
            return
    
    # 2. List all databases user has access to
    print("\n2. Listing accessible databases...")
    async with httpx.AsyncClient() as client:
        try:
            # Correct usage for POST request with JSON body
            response = await client.post(
                "https://api.notion.com/v1/search", 
                headers=headers, 
                json={"filter": {"property": "object", "value": "database"}}
            )
            
            if response.status_code == 200:
                results = response.json().get("results", [])
                print(f"✓ Found {len(results)} databases")
                
                # Show the databases
                for idx, db in enumerate(results):
                    db_id_with_hyphens = db.get("id", "")
                    db_id_raw = db_id_with_hyphens.replace("-", "")
                    title_objects = db.get("title", [])
                    title = "Untitled"
                    if title_objects:
                        # Navigate the correct path to get the title
                        for obj in title_objects:
                            if "plain_text" in obj:
                                title = obj["plain_text"]
                                break
                    print(f"  {idx+1}. {title} - ID: {db_id_raw} (with hyphens: {db_id_with_hyphens})")
                
                # Check if our target database is in the list
                target_db_found = any(db.get("id", "").replace("-", "") == db_id for db in results)
                if target_db_found:
                    print(f"✓ Target database ({db_id}) is in the list")
                else:
                    print(f"✗ Target database ({db_id}) NOT FOUND in the list")
                    print("  This means your integration doesn't have access to this database")
            else:
                print(f"✗ Failed to list databases: {response.status_code}")
                print(f"  Response: {response.text}")
        except Exception as e:
            print(f"✗ Error listing databases: {e}")
    
    # 3. Try to query the specific database
    print(f"\n3. Testing access to database {db_id}...")
    async with httpx.AsyncClient() as client:
        try:
            # This is where we need to ensure no hyphens are added
            url = f"https://api.notion.com/v1/databases/{db_id}/query"
            response = await client.post(url, headers=headers, json={"page_size": 1})
            
            if response.status_code == 200:
                print(f"✓ Successfully accessed the database!")
                results = response.json().get("results", [])
                print(f"  Found {len(results)} results")
            else:
                print(f"✗ Failed to access database: {response.status_code}")
                print(f"  Response: {response.text}")
                print("\nNote: If you're seeing a 404, make sure:")
                print("1. Your database ID is correct")
                print("2. You've shared the database with your integration")
                print("3. Your integration has the proper capabilities")
        except Exception as e:
            print(f"✗ Error accessing database: {e}")

if __name__ == "__main__":
    asyncio.run(test_notion_api())