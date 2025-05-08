# backend/update_formula_docs.py

import asyncio
import sys
import os
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import models
from app.config import settings

# Ensure Notion IDs are correctly formatted with hyphens
def format_notion_id(notion_id):
    """
    Format Notion IDs correctly.
    Note: For API calls, we need to use the raw ID without any hyphens.
    """
    if not notion_id:
        return notion_id
        
    # Remove any hyphens - Notion API wants IDs without hyphens
    return notion_id.replace("-", "")
async def update_all_formulas():
    """
    Updates all formulas without MSDS or SOP.
    """
    # Format Notion IDs correctly
    os.environ["NOTION_FORMULAS_DB_ID"] = format_notion_id(os.environ.get("NOTION_FORMULAS_DB_ID", ""))
    os.environ["NOTION_DOCS_DB_ID"] = format_notion_id(os.environ.get("NOTION_DOCS_DB_ID", ""))
    
    # Print debug info
    print(f"Using Notion Formulas DB ID: {os.environ['NOTION_FORMULAS_DB_ID']}")
    print(f"Using Notion Docs DB ID: {os.environ['NOTION_DOCS_DB_ID']}")
    
    db = SessionLocal()
    try:
        # Get all formulas
        formulas = db.query(models.Formula).all()
        print(f"Found {len(formulas)} formulas")
        
        updated_count = 0
        for formula in formulas:
            # Check if formula is missing MSDS or SOP
            if not formula.msds or not formula.sop:
                print(f"Updating formula: {formula.name} (ID: {formula.id})")
                
                # Generate placeholder MSDS if missing
                if not formula.msds:
                    formula.msds = (
                        f"# Material Safety Data Sheet for {formula.name}\n\n"
                        "## 1. Product and Company Identification\n"
                        f"Product Name: {formula.name}\n"
                        "Product Type: Cosmetic Formulation\n"
                        "Recommended Use: Personal Care\n\n"
                        "## 2. Hazards Identification\n"
                        "This is a personal care product that is safe for consumers when used according to the label directions.\n\n"
                        "## 3. Composition/Information on Ingredients\n"
                        "Mixture of cosmetic ingredients. See formula ingredient list for details.\n\n"
                        "## 4. First Aid Measures\n"
                        "Eye Contact: Flush with water. Seek medical attention if irritation persists.\n"
                        "Skin Contact: Discontinue use if irritation occurs. Wash with water.\n"
                        "Ingestion: Contact a physician or poison control center.\n\n"
                        "## 5. Handling and Storage\n"
                        "Store in a cool, dry place away from direct sunlight.\n"
                        "Keep out of reach of children.\n\n"
                        "## 6. Disposal Considerations\n"
                        "Dispose of in accordance with local regulations."
                    )
                
                # Generate placeholder SOP if missing
                if not formula.sop:
                    formula.sop = (
                        f"# Standard Operating Procedure for {formula.name}\n\n"
                        "## 1. Equipment and Materials\n"
                        "- Digital scale (precision 0.1g)\n"
                        "- Water bath or double boiler\n"
                        "- Thermometer (0-100°C)\n"
                        "- Glass beakers (various sizes)\n"
                        "- Overhead stirrer or homogenizer\n"
                        "- pH meter\n"
                        "- Clean spatulas and utensils\n"
                        "- Sterilized packaging containers\n\n"
                        
                        "## 2. Sanitation Procedures\n"
                        "- Sanitize all equipment with 70% isopropyl alcohol\n"
                        "- Ensure clean workspace and wear appropriate PPE\n"
                        "- Use purified water for all formulation steps\n\n"
                        
                        "## 3. Manufacturing Process\n"
                        "Follow the manufacturing steps provided in the formula details.\n\n"
                        
                        "## 4. Quality Control\n"
                        "- Check appearance, color, and odor\n"
                        "- Verify pH is appropriate for product type\n"
                        "- Perform stability testing at various temperatures\n"
                        "- Check viscosity and texture\n\n"
                        
                        "## 5. Packaging and Storage\n"
                        "- Fill containers at appropriate temperature\n"
                        "- Seal containers immediately after filling\n"
                        "- Store in cool, dry place away from direct sunlight\n"
                        "- Label with batch number and production date\n\n"
                        
                        "## 6. Troubleshooting\n"
                        "- If separation occurs: Check emulsifier percentage and mixing process\n"
                        "- If viscosity issues: Adjust thickener concentration\n"
                        "- If preservation issues: Check pH and preservative system"
                    )
                
                db.commit()
                updated_count += 1
        
        print(f"Updated documentation for {updated_count} formulas")
        
        # Only try to sync to Notion if we have the correct settings
        if os.environ.get("NOTION_API_KEY") and os.environ.get("NOTION_FORMULAS_DB_ID"):
            # Now sync one formula at a time
            for formula in formulas:
                try:
                    print(f"\nTesting Notion access to database {os.environ['NOTION_FORMULAS_DB_ID']}...")
                    from app.services.notion_service import NotionService
                    
                    notion_service = NotionService(db)
                    # Try to query the database first to verify access
                    try:
                        result = await notion_service._make_request(
                            "post",
                            f"databases/{os.environ['NOTION_FORMULAS_DB_ID']}/query",
                            {"page_size": 1}
                        )
                        print("✓ Successfully connected to Notion database")
                        
                        # If we got here, we can try syncing
                        print(f"Syncing formula {formula.id} to Notion...")
                        await notion_service.sync_formula_to_notion(formula.id, formula.user_id)
                        print(f"✓ Successfully synced formula {formula.id} to Notion")
                    except Exception as e:
                        print(f"✗ Error accessing Notion database: {str(e)}")
                        print("  Please make sure you have shared the database with your integration.")
                        break
                except Exception as e:
                    print(f"Error syncing formula {formula.id} to Notion: {str(e)}")
        else:
            print("\nSkipping Notion sync - API key or database ID not configured.")
                
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(update_all_formulas())