# backend/app/services/openai_service.py
import os
import openai
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app import models, schemas

# Set OpenAI API key from environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

class OpenAIFormulaGenerator:
    """Service for generating cosmetic formulas using OpenAI's API."""
    
    def __init__(self, db: Session):
        self.db = db
        
    async def generate_formula(
        self,
        product_type: str,
        skin_concerns: List[str],
        user_subscription: models.SubscriptionType,
        preferred_ingredients: Optional[List[int]] = None,
        avoided_ingredients: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Generate a complete cosmetic formula using OpenAI.
        
        Args:
            product_type: Type of cosmetic product (serum, moisturizer, etc.)
            skin_concerns: List of skin concerns to address
            user_subscription: User's subscription level
            preferred_ingredients: Optional list of preferred ingredient IDs
            avoided_ingredients: Optional list of avoided ingredient IDs
            
        Returns:
            Dictionary containing the generated formula data
        """
        # Get available ingredients based on subscription tier
        available_ingredients = self._get_available_ingredients(user_subscription)
        
        # Get preferred and avoided ingredient details
        preferred_ingredient_details = self._get_ingredient_details(preferred_ingredients) if preferred_ingredients else []
        avoided_ingredient_details = self._get_ingredient_details(avoided_ingredients) if avoided_ingredients else []
        
        # Build the prompt for OpenAI
        prompt = self._build_formula_prompt(
            product_type,
            skin_concerns,
            available_ingredients,
            preferred_ingredient_details,
            avoided_ingredient_details
        )
        
        try:
            # Call OpenAI API to generate the formula
            response = await self._call_openai_api(prompt)
            
            # Parse the response to get structured formula data
            formula_data = self._parse_formula_response(response)
            
            # Validate the generated formula
            self._validate_formula(formula_data)
            
            return formula_data
            
        except Exception as e:
            # Log the error
            print(f"Error generating formula with OpenAI: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Error generating formula: {str(e)}"
            )
    
    def _get_available_ingredients(self, user_subscription: models.SubscriptionType) -> List[Dict[str, Any]]:
        """Get list of ingredients available for the user's subscription tier."""
        query = self.db.query(models.Ingredient)
        
        # Filter ingredients based on subscription level
        if user_subscription == models.SubscriptionType.FREE:
            query = query.filter(
                models.Ingredient.is_premium.is_(False),
                models.Ingredient.is_professional.is_(False)
            )
        elif user_subscription == models.SubscriptionType.PREMIUM:
            query = query.filter(models.Ingredient.is_professional.is_(False))
        
        ingredients = query.all()
        
        # Convert to list of dictionaries with necessary fields
        return [
            {
                "id": ing.id,
                "name": ing.name,
                "inci_name": ing.inci_name,
                "phase": ing.phase,
                "function": ing.function,
                "max_percentage": ing.recommended_max_percentage,
                "solubility": ing.solubility
            }
            for ing in ingredients
        ]
    
    def _get_ingredient_details(self, ingredient_ids: List[int]) -> List[Dict[str, Any]]:
        """Get details for specific ingredients by their IDs."""
        ingredients = self.db.query(models.Ingredient).filter(
            models.Ingredient.id.in_(ingredient_ids)
        ).all()
        
        return [
            {
                "id": ing.id,
                "name": ing.name,
                "inci_name": ing.inci_name,
                "phase": ing.phase,
                "function": ing.function
            }
            for ing in ingredients
        ]
    
    def _build_formula_prompt(
            self,
            product_type: str,
            skin_concerns: List[str],
            available_ingredients: List[Dict[str, Any]],
            preferred_ingredients: List[Dict[str, Any]],
            avoided_ingredients: List[Dict[str, Any]]
        ) -> str:
            """
            Build a detailed prompt for OpenAI to generate a cosmetic formula.
            """
            # Basic prompt structure
            prompt = f"""
    You are a professional cosmetic formulator with expertise in creating safe, effective, and stable cosmetic products.
    I need you to create a complete formula for a {product_type.lower()} that addresses the following skin concerns: {', '.join(skin_concerns)}.

    THE FORMULA SHOULD FOLLOW THESE GUIDELINES:
    1. Total percentage of all ingredients must equal exactly 100%.
    2. Include appropriate preservatives for product stability and safety.
    3. Follow proper formulation principles for the specific product type.
    4. Include appropriate ingredients for the specified skin concerns.
    5. The formula should have proper phase separation (water phase, oil phase, cool down phase, etc.).
    6. Follow cosmetic chemistry best practices regarding pH, emulsion stability, etc.

    PRODUCT SPECIFICATIONS:
    - Product type: {product_type.upper()}
    - Skin concerns to address: {', '.join(skin_concerns)}
    """

            # Add preferred ingredients if any
            if preferred_ingredients:
                prompt += "\nPREFERRED INGREDIENTS (please try to include these if suitable):\n"
                for ing in preferred_ingredients:
                    prompt += f"- ID: {ing['id']}, {ing['name']} ({ing['inci_name']}): {ing['function'] or 'Function not specified'}, {ing['phase'] or 'Phase not specified'}\n"
            
            # Add avoided ingredients if any
            if avoided_ingredients:
                prompt += "\nAVOIDED INGREDIENTS (please do not include these):\n"
                for ing in avoided_ingredients:
                    prompt += f"- ID: {ing['id']}, {ing['name']} ({ing['inci_name']})\n"
            
            # Add available ingredients categorized by phase
            phases = {}
            for ing in available_ingredients:
                phase = ing.get("phase") or "Uncategorized"
                if phase not in phases:
                    phases[phase] = []
                phases[phase].append(ing)
            
            prompt += "\nAVAILABLE INGREDIENTS BY PHASE:\n"
            for phase, ingredients in phases.items():
                prompt += f"\n{phase.upper()}:\n"
                for ing in ingredients[:20]:  # Limit to 20 ingredients per phase to avoid token limits
                    max_pct = f", max {ing['max_percentage']}%" if ing.get('max_percentage') else ""
                    function = f", {ing['function']}" if ing.get('function') else ""
                    prompt += f"- ID: {ing['id']}, {ing['name']} ({ing['inci_name']}){function}{max_pct}\n"
                
                if len(ingredients) > 20:
                    prompt += f"- ... and {len(ingredients) - 20} more ingredients\n"
            
            # Add instruction for the output format with EMPHASIS on using IDs
            prompt += """
    IMPORTANT: When creating the formula, you MUST use numeric ID values from the available ingredients list.
    DO NOT use ingredient names as IDs. Each ingredient in your formula must have a numeric ID that corresponds
    to an ingredient in the database.

    PLEASE PROVIDE THE FORMULA IN THE FOLLOWING JSON FORMAT:
    {
    "name": "Name of the Formula",
    "description": "Description addressing the benefits and skin concerns",
    "ingredients": [
        {
        "ingredient_id": ID_NUMBER,
        "percentage": PERCENTAGE_VALUE,
        "order": ORDER_NUMBER
        },
        ...
    ],
    "steps": [
        {
        "description": "Step 1 description",
        "order": 1
        },
        ...
    ]
    }

    Example of CORRECT ingredient format:
    "ingredients": [
    {"ingredient_id": 12, "percentage": 70.0, "order": 1},
    {"ingredient_id": 45, "percentage": 15.0, "order": 2},
    {"ingredient_id": 23, "percentage": 10.0, "order": 3},
    {"ingredient_id": 67, "percentage": 5.0, "order": 4}
    ]

    Example of INCORRECT ingredient format (DO NOT DO THIS):
    "ingredients": [
    {"ingredient_id": "Distilled Water", "percentage": 70.0, "order": 1},
    {"ingredient_id": "Glycerin", "percentage": 15.0, "order": 2}
    ]

    The ingredient_id MUST be a numeric ID from the available ingredients list.
    Please ensure the formula follows proper formulation practices and the total percentage equals exactly 100%.
    """
            
            return prompt    
    async def _call_openai_api(self, prompt: str) -> str:
        """
        Call OpenAI API with the given prompt.
        """
        try:
            # Use ChatCompletion for better structured responses
            response = await openai.ChatCompletion.acreate(
                model="gpt-4",  # Use GPT-4 for more accurate formulations
                messages=[
                    {"role": "system", "content": "You are a professional cosmetic formulator with expertise in creating safe, effective, and stable cosmetic products."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000,
                top_p=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.0
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"OpenAI API call failed: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"AI service error: {str(e)}"
            )
    
    
    def _parse_formula_response(self, response: str) -> Dict[str, Any]:
        """
        Parse the OpenAI response to extract structured formula data and map
        ingredient names to IDs if needed.
        """
        try:
            import json
            import re
            
            # Extract JSON from the response
            json_pattern = r'\{[\s\S]*\}'
            match = re.search(json_pattern, response)
            
            if not match:
                raise ValueError("Could not find valid JSON in the response")
            
            json_str = match.group(0)
            formula_data = json.loads(json_str)
            
            # Make sure all required fields are present
            required_fields = ["name", "description", "ingredients", "steps"]
            for field in required_fields:
                if field not in formula_data:
                    raise ValueError(f"Missing required field in formula data: {field}")
            
            # Process ingredients - map names to IDs if needed
            if "ingredients" in formula_data:
                processed_ingredients = []
                for idx, ingredient in enumerate(formula_data["ingredients"]):
                    # Check if the ingredient is specified by name instead of ID
                    if isinstance(ingredient.get("ingredient_id"), str):
                        ingredient_name = ingredient.get("ingredient_id")
                        ingredient_id = self._find_ingredient_id_by_name(ingredient_name)
                        if ingredient_id:
                            processed_ingredients.append({
                                "ingredient_id": ingredient_id,
                                "percentage": ingredient.get("percentage", 5.0),
                                "order": ingredient.get("order", idx + 1)
                            })
                    else:
                        processed_ingredients.append(ingredient)
                
                formula_data["ingredients"] = processed_ingredients
            
            return formula_data
                
        except Exception as e:
            print(f"Failed to parse OpenAI response: {str(e)}")
            print(f"Raw response: {response}")
            raise HTTPException(
                status_code=500, 
                detail="Failed to parse the generated formula data"
            )
    def _find_ingredient_id_by_name(self, name: str) -> Optional[int]:
        """
        Find an ingredient ID by its name or INCI name.
        
        Args:
            name: The ingredient name to search for
            
        Returns:
            The ingredient ID if found, None otherwise
        """
        if not name:
            return None
            
        # Clean up the name (remove parentheses parts if needed)
        cleaned_name = name.split("(")[0].strip()
        
        # Try to find the ingredient in the database by exact name
        ingredient = self.db.query(models.Ingredient).filter(
            models.Ingredient.name == cleaned_name
        ).first()
        
        if ingredient:
            return ingredient.id
        
        # Try with case-insensitive match
        ingredient = self.db.query(models.Ingredient).filter(
            models.Ingredient.name.ilike(f"{cleaned_name}")
        ).first()
        
        if ingredient:
            return ingredient.id
        
        # Try with partial match
        ingredient = self.db.query(models.Ingredient).filter(
            models.Ingredient.name.ilike(f"%{cleaned_name}%")
        ).first()
        
        if ingredient:
            return ingredient.id
        
        # Try to find by INCI name if not found by regular name
        ingredient = self.db.query(models.Ingredient).filter(
            models.Ingredient.inci_name.ilike(f"%{cleaned_name}%")
        ).first()
        
        if ingredient:
            return ingredient.id
        
        # Last resort: Try to match by word parts 
        name_parts = cleaned_name.lower().split()
        if len(name_parts) > 1:
            # Try to find ingredients that match at least one part of the name
            for part in name_parts:
                if len(part) > 3:  # Only try with parts that are reasonably long
                    ingredient = self.db.query(models.Ingredient).filter(
                        models.Ingredient.name.ilike(f"%{part}%")
                    ).first()
                    
                    if ingredient:
                        return ingredient.id
        
        return None

    
    
    def _validate_formula(self, formula_data: Dict[str, Any]) -> None:
        """
        Validate the generated formula data to ensure it meets requirements,
        including mapping string ingredient IDs to numeric IDs if needed.
        """
        # Check if there are ingredients
        if "ingredients" not in formula_data or not formula_data["ingredients"]:
            raise ValueError("Formula contains no ingredients")
                
        # Process ingredients - map string IDs to numeric IDs if needed
        processed_ingredients = []
        for idx, ing in enumerate(formula_data["ingredients"]):
            ing_id = ing.get("ingredient_id")
            
            # Handle string IDs by trying to find matching ingredient
            if isinstance(ing_id, str):
                db_id = self._find_ingredient_id_by_name(ing_id)
                if db_id:
                    ing["ingredient_id"] = db_id
                    processed_ingredients.append(ing)
                else:
                    print(f"Warning: Could not find ingredient ID for '{ing_id}'")
            else:
                processed_ingredients.append(ing)
        
        formula_data["ingredients"] = processed_ingredients
        
        # Check if we have any valid ingredients left
        if not formula_data["ingredients"]:
            raise ValueError("No valid ingredients found after processing")
        
        # Check ingredient percentages sum to 100%
        total_percentage = sum(ing["percentage"] for ing in formula_data["ingredients"])
        if not (99.5 <= total_percentage <= 100.5):  # Allow small rounding errors
            # Adjust percentages to sum to 100%
            adjustment_factor = 100.0 / total_percentage
            for ing in formula_data["ingredients"]:
                ing["percentage"] = round(ing["percentage"] * adjustment_factor, 1)
            print(f"Adjusted ingredient percentages from {total_percentage}% to 100%")
        
        # Verify the ingredients exist in database
        ingredient_ids = [ing["ingredient_id"] for ing in formula_data["ingredients"]]
        existing_ingredients = self.db.query(models.Ingredient.id).filter(
            models.Ingredient.id.in_(ingredient_ids)
        ).all()
        existing_ids = [ing[0] for ing in existing_ingredients]
        
        missing_ids = set(ingredient_ids) - set(existing_ids)
        if missing_ids:
            raise ValueError(f"Invalid ingredient IDs: {missing_ids}")
        
        # Check steps
        if "steps" not in formula_data or not formula_data["steps"]:
            raise ValueError("Formula contains no steps")