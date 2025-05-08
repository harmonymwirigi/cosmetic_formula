# backend/app/api/endpoints/notion.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import models, schemas
from app.database import get_db
from app.auth import get_current_user
from app.services.notion_service import NotionService, sync_all_formulas
from typing import Dict, Any, List
import os
from app.config import settings

router = APIRouter()

@router.get("/status", response_model=Dict[str, Any])
async def get_notion_status(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check Notion integration status for the current user.
    """
    # Get user's Notion integration
    notion_integration = db.query(models.NotionIntegration).filter(
        models.NotionIntegration.user_id == current_user.id
    ).first()
    
    # Check if the API key is set
    api_key = os.getenv("NOTION_API_KEY", settings.NOTION_API_KEY)
    is_api_key_set = bool(api_key)
    
    # Return status
    return {
        "is_connected": bool(notion_integration),
        "database_id": notion_integration.formulas_db_id if notion_integration else None,
        "api_key_set": is_api_key_set,
        "last_synced": notion_integration.updated_at if notion_integration else None
    }

@router.post("/connect", response_model=Dict[str, Any])
async def connect_notion(
    data: Dict[str, Any],
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Configure Notion integration for the current user.
    
    This endpoint uses the global Notion API key but creates a new database
    for the user if they don't have one already.
    """
    # Check if the API key is set
    api_key = os.getenv("NOTION_API_KEY", settings.NOTION_API_KEY)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Notion API key is not configured. Please set NOTION_API_KEY environment variable."
        )
    
    # Get database name
    database_name = data.get("database_name", "Cosmetic Formula Database")
    
    try:
        # Initialize Notion service
        notion_service = NotionService(db)
        
        # First check if the user already has a Notion integration
        existing_integration = db.query(models.NotionIntegration).filter(
            models.NotionIntegration.user_id == current_user.id
        ).first()
        
        if existing_integration:
            # Return the existing integration
            return {
                "success": True,
                "message": "Notion integration already configured",
                "database_id": existing_integration.formulas_db_id
            }
        
        # Create a new integration with the default settings
        integration = models.NotionIntegration(
            user_id=current_user.id,
            access_token=api_key,
            workspace_id="",  # Leave empty for default workspace
            formulas_db_id=notion_service.formulas_db_id,
            docs_db_id=notion_service.docs_db_id
        )
        
        db.add(integration)
        db.commit()
        db.refresh(integration)
        
        return {
            "success": True,
            "message": "Connected to Notion successfully",
            "database_id": integration.formulas_db_id
        }
    
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to connect to Notion: {str(e)}"
        )

@router.delete("/disconnect", response_model=Dict[str, Any])
async def disconnect_notion(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Disconnect Notion integration for the current user.
    """
    try:
        # Delete the user's Notion integration
        result = db.query(models.NotionIntegration).filter(
            models.NotionIntegration.user_id == current_user.id
        ).delete()
        
        db.commit()
        
        if result == 0:
            return {
                "success": False,
                "message": "No Notion integration found to disconnect"
            }
        
        return {
            "success": True,
            "message": "Disconnected from Notion successfully"
        }
    
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disconnect from Notion: {str(e)}"
        )

@router.post("/sync-formula/{formula_id}", response_model=Dict[str, Any])
async def sync_formula(
    formula_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Sync a specific formula to Notion.
    """
    try:
        # Get the formula
        formula = db.query(models.Formula).filter(
            models.Formula.id == formula_id,
            models.Formula.user_id == current_user.id
        ).first()
        
        if not formula:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Formula not found or not authorized"
            )
        
        # Initialize Notion service
        notion_service = NotionService(db)
        
        # Sync the formula
        result = await notion_service.sync_formula_to_notion(formula_id, current_user.id)
        
        return {
            "success": True,
            "formula_id": formula_id,
            "formula_name": formula.name,
            "notion_page_id": result["notion_page_id"],
            "notion_url": result.get("notion_url")
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync formula to Notion: {str(e)}"
        )

@router.post("/sync-all", response_model=Dict[str, Any])
async def sync_all_formulas_to_notion(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Sync all formulas for the current user to Notion.
    """
    try:
        # Sync all formulas
        results = await sync_all_formulas(db, current_user.id)
        
        # Count successful and failed syncs
        successful = sum(1 for r in results if r["success"])
        failed = len(results) - successful
        
        return {
            "success": True,
            "message": f"Synced {successful} formulas to Notion. {failed} failed.",
            "results": results
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync formulas to Notion: {str(e)}"
        )