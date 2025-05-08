# backend/app/services/notion_service.py

import os
import json
import asyncio
from typing import Dict, Any, List, Optional
import httpx
from sqlalchemy.orm import Session
from app import models, schemas
from app.config import settings
from datetime import datetime

class NotionService:
    """
    Service to synchronize formulas and documentation with Notion.
    """
    
    def __init__(self, db: Session):
        self.db = db
        # Get API key from environment variables or settings
        self.api_key = os.getenv("NOTION_API_KEY", settings.NOTION_API_KEY)
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }
        
        # Use database IDs without hyphens
        self.formulas_db_id = self._normalize_notion_id(os.getenv("NOTION_FORMULAS_DB_ID", settings.NOTION_FORMULAS_DB_ID))
        self.docs_db_id = self._normalize_notion_id(os.getenv("NOTION_DOCS_DB_ID", settings.NOTION_DOCS_DB_ID))
        
        # Print database IDs for debugging
        print(f"DEBUG: formulas_db_id = {self.formulas_db_id}")
        print(f"DEBUG: docs_db_id = {self.docs_db_id}")
    
    def _normalize_notion_id(self, notion_id):
        """Ensure Notion IDs have the correct format for API requests"""
        if not notion_id:
            return notion_id
            
        # First, remove any existing hyphens
        notion_id = notion_id.replace("-", "")
        
        # Format with hyphens: 8-4-4-4-12 pattern
        if len(notion_id) == 32:
            return f"{notion_id[0:8]}-{notion_id[8:12]}-{notion_id[12:16]}-{notion_id[16:20]}-{notion_id[20:]}"
        
        return notion_id
    

    async def _make_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make an async request to the Notion API.
        """
        # Fix endpoint to ensure database IDs have correct formatting
        if "databases/" in endpoint:
            # Split the endpoint to get the database ID
            parts = endpoint.split("databases/")
            prefix = parts[0] + "databases/"
            suffix_parts = parts[1].split("/", 1)
            db_id = self._normalize_notion_id(suffix_parts[0])  # Format the ID correctly
            if len(suffix_parts) > 1:
                endpoint = prefix + db_id + "/" + suffix_parts[1]
            else:
                endpoint = prefix + db_id
        
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}/{endpoint}"
            print(f"DEBUG: Making {method.upper()} request to {url}")
            
            # Debug print the request data
            if data:
                print(f"DEBUG: Request data parent: {data.get('parent', 'MISSING')}")
            
            if method.lower() == "get":
                response = await client.get(url, headers=self.headers)
            elif method.lower() == "post":
                response = await client.post(url, headers=self.headers, json=data)
            elif method.lower() == "patch":
                response = await client.patch(url, headers=self.headers, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            if response.status_code >= 400:
                raise Exception(f"Notion API error: {response.status_code} - {response.text}")
            
            return response.json()
    
    async def get_user_notion_integration(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get Notion integration settings for a user.
        Since we're auto-connecting to Notion, we'll use the default settings.
        """
        # Check if a user-specific integration exists
        notion_settings = self.db.query(models.NotionIntegration).filter(
            models.NotionIntegration.user_id == user_id
        ).first()
        
        if notion_settings:
            return {
                "access_token": notion_settings.access_token,
                "workspace_id": notion_settings.workspace_id,
                "formulas_db_id": notion_settings.formulas_db_id,
                "docs_db_id": notion_settings.docs_db_id
            }
        
        # If not, create a default integration for this user with global settings
        integration = models.NotionIntegration(
            user_id=user_id,
            access_token=self.api_key,  # Use the global API key
            workspace_id="",  # Leave empty for default workspace
            formulas_db_id=self.formulas_db_id,
            docs_db_id=self.docs_db_id
        )
        
        try:
            self.db.add(integration)
            self.db.commit()
            self.db.refresh(integration)
            
            return {
                "access_token": integration.access_token,
                "workspace_id": integration.workspace_id,
                "formulas_db_id": integration.formulas_db_id,
                "docs_db_id": integration.docs_db_id
            }
        except Exception as e:
            print(f"Error creating Notion integration: {str(e)}")
            # Return default values
            return {
                "access_token": self.api_key,
                "workspace_id": "",
                "formulas_db_id": self.formulas_db_id,
                "docs_db_id": self.docs_db_id
            }
    
    def _format_formula_for_notion(self, formula: models.Formula) -> Dict[str, Any]:
        """
        Format formula data for Notion database.
        """
        # Get formula ingredients directly from the database using the association table
        from sqlalchemy import text
        sql = text(f"SELECT i.id, i.name, fi.percentage, fi.order, i.phase FROM ingredients i "
                 f"JOIN formula_ingredients fi ON i.id = fi.ingredient_id "
                 f"WHERE fi.formula_id = :formula_id "
                 f"ORDER BY fi.order")
        
        ingredients_result = self.db.execute(sql, {"formula_id": formula.id}).fetchall()
        
        # Process ingredients from the query result
        ingredients = []
        for ing in ingredients_result:
            ingredients.append({
                "id": ing.id,
                "name": ing.name,
                "percentage": ing.percentage,
                "order": ing.order,
                "phase": ing.phase or "Uncategorized"
            })
        
        # Debug - print the ingredients we found
        print(f"DEBUG: Found {len(ingredients)} ingredients for formula {formula.id}")
        for ing in ingredients:
            print(f"DEBUG: Ingredient {ing['name']} - {ing['percentage']}%")
        
        # Create step list blocks - fix for the sorting issue
        step_blocks = []
        if formula.steps and len(formula.steps) > 0:
            # Sort steps by order
            sorted_steps = sorted(formula.steps, key=lambda s: s.order)
            
            for step in sorted_steps:
                step_blocks.append({
                    "object": "block",
                    "type": "numbered_list_item",
                    "numbered_list_item": {
                        "rich_text": [
                            {
                                "text": {
                                    "content": step.description
                                }
                            }
                        ]
                    }
                })
        else:
            # Add a placeholder if no steps
            step_blocks = [{
                "object": "block",
                "type": "numbered_list_item",
                "numbered_list_item": {
                    "rich_text": [
                        {
                            "text": {
                                "content": "Manufacturing steps will be added here"
                            }
                        }
                    ]
                }
            }]
        
        # Get the current date in proper format
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # Format data for Notion
        formatted_data = {
            "parent": {"database_id": self.formulas_db_id},
            "properties": {
                "Name": {
                    "title": [
                        {
                            "text": {
                                "content": formula.name
                            }
                        }
                    ]
                },
                # Add the Date property - Notion requires ISO format dates
                "Date": {
                    "date": {
                        "start": current_date
                    }
                }
            },
            "children": [
                # Ingredients Section
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{
                            "text": {
                                "content": "Ingredients"
                            }
                        }]
                    }
                },
                {
                    "object": "block",
                    "type": "table",
                    "table": {
                        "table_width": 3,
                        "has_column_header": True,
                        "has_row_header": False,
                        "children": [
                            # Header row
                            {
                                "type": "table_row",
                                "table_row": {
                                    "cells": [
                                        [{"text": {"content": "Ingredient"}}],
                                        [{"text": {"content": "Percentage"}}],
                                        [{"text": {"content": "Order"}}]
                                    ]
                                }
                            },
                            # Data rows
                            *[{
                                "type": "table_row",
                                "table_row": {
                                    "cells": [
                                        [{"text": {"content": ing.get("name", "")}}],
                                        [{"text": {"content": f"{ing.get('percentage', 0)}%"}}],
                                        [{"text": {"content": str(ing.get("order", 0))}}]
                                    ]
                                }
                            } for ing in ingredients]
                        ]
                    }
                },
                # Steps Section
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{
                            "text": {
                                "content": "Manufacturing Steps"
                            }
                        }]
                    }
                },
                # Add steps with the fixed approach
                *step_blocks,
                
                # MSDS Section
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{
                            "text": {
                                "content": "Material Safety Data Sheet (MSDS)"
                            }
                        }]
                    }
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "text": {
                                    "content": formula.msds or "No MSDS information available."
                                }
                            }
                        ]
                    }
                },
                # SOP Section
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{
                            "text": {
                                "content": "Standard Operating Procedure (SOP)"
                            }
                        }]
                    }
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "text": {
                                    "content": formula.sop or "No SOP information available."
                                }
                            }
                        ]
                    }
                }
            ]
        }
        
        # Debug print to verify formatted data
        print(f"DEBUG: formatted_data parent: {formatted_data.get('parent')}")
        print(f"DEBUG: formatted_data properties keys: {list(formatted_data['properties'].keys())}")
        
        return formatted_data
    
    async def sync_formula_to_notion(self, formula_id: int, user_id: int) -> Dict[str, Any]:
        """
        Sync a formula to Notion.
        """
        # Get the formula
        formula = self.db.query(models.Formula).filter(
            models.Formula.id == formula_id,
            models.Formula.user_id == user_id
        ).first()
        
        if not formula:
            raise ValueError("Formula not found or not authorized")
        
        # Get user's Notion settings
        notion_settings = await self.get_user_notion_integration(user_id)
        if not notion_settings:
            raise ValueError("Notion integration not set up for this user")
        
        # Use user's database ID if available - make sure it's correctly formatted
        self.formulas_db_id = notion_settings.get("formulas_db_id") or self.formulas_db_id
        # Ensure database ID is correctly formatted
        self.formulas_db_id = self._normalize_notion_id(self.formulas_db_id)
        
        print(f"DEBUG: Using formulas_db_id in sync: {self.formulas_db_id}")
        
        # Check if formula already exists in Notion
        notion_formula = await self._find_formula_in_notion(formula_id, user_id)
        
        # Format data for Notion
        formatted_data = self._format_formula_for_notion(formula)
        
        # Double-check that parent is correctly set
        if not formatted_data.get("parent") or not formatted_data["parent"].get("database_id"):
            print("WARNING: parent or database_id is missing in formatted data!")
            # Make sure it's there
            formatted_data["parent"] = {"database_id": self.formulas_db_id}
        
        if notion_formula:
            # Update existing page
            page_id = notion_formula["id"]
            result = await self._make_request(
                "patch", 
                f"pages/{page_id}", 
                {
                    "properties": formatted_data["properties"],
                    # Cannot update children directly with patch, need separate API call
                }
            )
            
            # Update content blocks
            await self._make_request(
                "patch", 
                f"blocks/{page_id}/children", 
                {"children": formatted_data["children"]}
            )
        else:
            # Create new page - make sure parent is included
            print(f"DEBUG: Creating new page with database_id: {formatted_data['parent']['database_id']}")
            result = await self._make_request(
                "post", 
                "pages", 
                formatted_data
            )
        
        # Save the Notion page ID to our database
        self._save_notion_page_id(formula_id, result["id"])
        
        return {
            "success": True,
            "notion_page_id": result["id"],
            "notion_url": result.get("url")
        }
    
    async def _find_formula_in_notion(self, formula_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Find a formula in Notion by name instead of Formula ID.
        """
        # Get the formula to find its name
        formula = self.db.query(models.Formula).filter(
            models.Formula.id == formula_id,
            models.Formula.user_id == user_id
        ).first()
        
        if not formula:
            return None
            
        # Get user's Notion settings
        notion_settings = await self.get_user_notion_integration(user_id)
        if not notion_settings:
            return None
        
        # Use user's database ID if available
        self.formulas_db_id = notion_settings.get("formulas_db_id") or self.formulas_db_id
        # Ensure database ID is correctly formatted
        self.formulas_db_id = self._normalize_notion_id(self.formulas_db_id)
        
        # Query Notion database for formula by name
        query_data = {
            "filter": {
                "property": "Name",
                "title": {
                    "contains": formula.name
                }
            }
        }
        
        try:
            result = await self._make_request(
                "post",
                f"databases/{self.formulas_db_id}/query",
                query_data
            )
            
            if result["results"]:
                return result["results"][0]
        except Exception as e:
            print(f"Error finding formula in Notion: {e}")
        
        return None
    
    def _save_notion_page_id(self, formula_id: int, notion_page_id: str):
        """
        Save the Notion page ID for a formula.
        """
        formula = self.db.query(models.Formula).filter(
            models.Formula.id == formula_id
        ).first()
        
        if formula:
            # Check if we have a NotionSync model
            notion_sync = self.db.query(models.NotionSync).filter(
                models.NotionSync.formula_id == formula_id
            ).first()
            
            if notion_sync:
                notion_sync.notion_page_id = notion_page_id
                notion_sync.last_synced = datetime.now()
            else:
                notion_sync = models.NotionSync(
                    formula_id=formula_id,
                    notion_page_id=notion_page_id,
                    last_synced=datetime.now()
                )
                self.db.add(notion_sync)
            
            self.db.commit()


async def sync_all_formulas(db: Session, user_id: int):
    """
    Sync all formulas for a user to Notion.
    """
    notion_service = NotionService(db)
    
    # Get all formulas for user
    formulas = db.query(models.Formula).filter(
        models.Formula.user_id == user_id
    ).all()
    
    results = []
    for formula in formulas:
        try:
            result = await notion_service.sync_formula_to_notion(formula.id, user_id)
            results.append({
                "formula_id": formula.id,
                "formula_name": formula.name,
                "success": True,
                "notion_page_id": result["notion_page_id"],
                "notion_url": result.get("notion_url")
            })
        except Exception as e:
            results.append({
                "formula_id": formula.id,
                "formula_name": formula.name,
                "success": False,
                "error": str(e)
            })
    
    return results