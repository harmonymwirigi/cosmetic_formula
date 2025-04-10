# backend/app/services/openai_service.py
import os
import json
from typing import List, Dict, Any, Optional, Union
import openai
from sqlalchemy.orm import Session
from app import models
from app.services.ai_formula import AIFormulaGenerator

# Configure OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

class OpenAIFormulaGenerator:
    """
    OpenAI-powered formula generator with tiered subscription prompts.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.rule_based_generator = AIFormulaGenerator(db)  # Fallback generator
    
    async def generate_formula(
        self,
        product_type: Union[str, Dict[str, Any]],
        skin_concerns: List[str],
        user_subscription: models.SubscriptionType,
        preferred_ingredients: Optional[List[int]] = None,
        avoided_ingredients: Optional[List[int]] = None,
        user_profile: Optional[Dict[str, Any]] = None,
        professional_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a formula using OpenAI based on subscription tier and preferences.
        
        Args:
            product_type: Type of product to generate (serum, moisturizer, etc.)
            skin_concerns: List of skin concerns from the request
            user_subscription: User's subscription tier
            preferred_ingredients: List of ingredient IDs to include
            avoided_ingredients: List of ingredient IDs to avoid
            user_profile: User's stored profile data (skin/hair details)
            professional_data: Professional tier brand information
            
        Returns:
            Dictionary with formula data
        """
        # Handle product_type being a dict (from frontend)
        if isinstance(product_type, dict):
            product_type = product_type.get("product_type", "moisturizer")
        
        # Get ingredient details for preferred/avoided ingredients
        preferred_ingredient_names = []
        avoided_ingredient_names = []
        
        if preferred_ingredients:
            ingredients = self.db.query(models.Ingredient).filter(
                models.Ingredient.id.in_(preferred_ingredients)
            ).all()
            preferred_ingredient_names = [ing.name for ing in ingredients]
        
        if avoided_ingredients:
            ingredients = self.db.query(models.Ingredient).filter(
                models.Ingredient.id.in_(avoided_ingredients)
            ).all()
            avoided_ingredient_names = [ing.name for ing in ingredients]
        
        # If we have a user profile, use the skin concerns from there if none provided in request
        if user_profile and not skin_concerns and user_profile.get('skin_concerns'):
            # Handle different types of skin_concerns
            if isinstance(user_profile['skin_concerns'], str):
                try:
                    skin_concerns = json.loads(user_profile['skin_concerns'])
                except:
                    skin_concerns = []
            elif isinstance(user_profile['skin_concerns'], list):
                skin_concerns = user_profile['skin_concerns']
            else:
                skin_concerns = []
        
        # Generate the appropriate prompt based on subscription tier and data
        prompt = self._generate_tiered_prompt(
            product_type,
            skin_concerns,
            user_subscription,
            preferred_ingredient_names,
            avoided_ingredient_names,
            user_profile,
            professional_data
        )
        
        try:
            # Call OpenAI
            response = await openai.ChatCompletion.acreate(
                model="gpt-4-turbo", # Or your preferred model
                messages=[
                    {"role": "system", "content": "You are an expert cosmetic chemist specializing in formulation development."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=1500,  # Reduced from 2500
                timeout=12,
                n=1,
                stop=None,
            )
            
            # Process the response
            ai_formula_text = response.choices[0].message.content
            
            # Parse the AI response into formula components
            formula_data = self._parse_formula_response(ai_formula_text, product_type)
            return formula_data
            
        except Exception as e:
            print(f"OpenAI API error: {str(e)}")
            # Fall back to rule-based generation
            return self.rule_based_generator.generate_formula(
                product_type,
                skin_concerns,
                user_subscription,
                preferred_ingredients,
                avoided_ingredients
            )
    
    def _generate_tiered_prompt(
        self,
        product_type: str,
        skin_concerns: List[str],
        user_subscription: models.SubscriptionType,
        preferred_ingredients: List[str],
        avoided_ingredients: List[str],
        user_profile: Optional[Dict[str, Any]],
        professional_data: Optional[Dict[str, Any]]
    ) -> str:
        """
        Generate a tiered prompt based on user subscription level.
        """
        # Ensure skin_concerns is a list of strings
        if not skin_concerns:
            skin_concerns = ["general skincare"]
        
        # Ensure user_profile is a dictionary
        if user_profile is None:
            user_profile = {}
        
        base_prompt = f"""
Generate a complete cosmetic formula for a {product_type} that addresses the following skin concerns: {', '.join(skin_concerns)}.
"""

        # Add profile data if available
        if user_profile:
            # Safely get skin_concerns and sensitivities as lists
            skin_concerns_list = []
            if 'skin_concerns' in user_profile:
                if isinstance(user_profile['skin_concerns'], list):
                    skin_concerns_list = user_profile['skin_concerns']
                elif isinstance(user_profile['skin_concerns'], str):
                    try:
                        skin_concerns_list = json.loads(user_profile['skin_concerns'])
                    except:
                        skin_concerns_list = []
            
            sensitivities_list = []
            if 'sensitivities' in user_profile:
                if isinstance(user_profile['sensitivities'], list):
                    sensitivities_list = user_profile['sensitivities']
                elif isinstance(user_profile['sensitivities'], str):
                    try:
                        sensitivities_list = json.loads(user_profile['sensitivities'])
                    except:
                        sensitivities_list = []
            
            profile_prompt = f"""
USER PROFILE:
Skin Type: {user_profile.get('skin_type', 'Not specified')}
Skin Concerns: {', '.join(skin_concerns_list) if skin_concerns_list else 'Not specified'}
Sensitivities/Allergies: {', '.join(sensitivities_list) if sensitivities_list else 'None'}
Climate: {user_profile.get('climate', 'Not specified')}
"""
            base_prompt += profile_prompt

        # Add ingredient preferences
        if preferred_ingredients:
            base_prompt += f"\nPreferred ingredients to include: {', '.join(preferred_ingredients)}."
            
        if avoided_ingredients:
            base_prompt += f"\nIngredients to avoid: {', '.join(avoided_ingredients)}."
        
        # Premium tier prompt
        if user_subscription == models.SubscriptionType.PREMIUM:
            premium_prompt = f"""
This is for a PREMIUM subscription user.

Please provide:
1. A descriptive name for the formula
2. A short description of the formula and its benefits
3. A complete list of ingredients with percentages (totaling 100%)
4. Proper phase separation (water phase, oil phase, cool-down phase, etc.)
5. Brief explanation of the key active ingredients and their benefits
6. Step-by-step manufacturing instructions
7. Expected texture and sensory properties

Format the response as follows:
- FORMULA NAME: [Name]
- DESCRIPTION: [Description]
- INGREDIENTS: [List each ingredient with percentage, INCI name, and phase]
- MANUFACTURING STEPS: [Numbered list of steps]
- NOTES: [Any additional notes about usage, stability, etc.]
"""
            return base_prompt + premium_prompt
            
        # Professional tier prompt
        elif user_subscription == models.SubscriptionType.PROFESSIONAL:
            # Get brand info from professional data
            brand_name = professional_data.get('brand_name', 'Not specified') if professional_data else 'Not specified'
            target_audience = professional_data.get('target_audience', 'Not specified') if professional_data else 'Not specified'
            target_markets = ', '.join(professional_data.get('target_markets', [])) if professional_data and professional_data.get('target_markets') else 'Global'
            brand_positioning = professional_data.get('brand_positioning', 'Not specified') if professional_data else 'Not specified'
            
            professional_prompt = f"""
This is for a PROFESSIONAL subscription user developing a commercial product.

Brand Information:
- Brand Name: {brand_name}
- Target Audience: {target_audience}
- Target Markets: {target_markets}
- Brand Positioning: {brand_positioning}

Please provide a commercial-grade formulation including:
1. A market-appropriate name for the formula
2. Comprehensive product description with key claims
3. Complete INCI list with precise percentages (totaling 100%)
4. Full phase separation with manufacturing temperatures and conditions
5. Detailed explanation of ingredient functions, interactions, and benefits
6. Alternative ingredients for cost optimization or natural variants
7. pH adjustment guidelines and preservation system details
8. Stability considerations and packaging recommendations
9. Manufacturing scale-up considerations
10. Marketing claim substantiation points
11. Recommended testing protocols

Format the response as follows:
- FORMULA NAME: [Name]
- PRODUCT DESCRIPTION: [Description with key claims]
- FORMULA OVERVIEW: [Brief overview of formulation approach]
- INGREDIENTS: [Detailed list with percentages, INCI names, phases, and functions]
- MANUFACTURING PROCESS: [Detailed process with temperatures and equipment]
- ALTERNATIVE INGREDIENTS: [Options for substitutions]
- REGULATORY CONSIDERATIONS: [pH, preservation, stability, claims support]
- PACKAGING & SCALE-UP: [Recommendations for packaging and production]
- TESTING PROTOCOLS: [Suggested tests for quality control]
- MARKETING COPY: [Short marketing blurb aligned with brand voice]
"""
            return base_prompt + professional_prompt
            
        # Default prompt (should not be reached with current implementation)
        else:
            return base_prompt + "\nPlease provide a basic formulation with ingredients and steps."
    
    def _parse_formula_response(self, ai_response: str, product_type: str) -> Dict[str, Any]:
        """
        Parse the OpenAI response into structured formula data.
        """
        # Ensure product_type is a string
        if isinstance(product_type, dict):
            product_type = product_type.get("product_type", "formula")
        
        # Initialize formula data
        formula_data = {
            "name": f"AI-Generated {product_type.title()}",
            "description": "",
            "ingredients": [],
            "steps": []
        }
        
        # Parse name
        name_match = None
        if "FORMULA NAME:" in ai_response:
            name_sections = ai_response.split("FORMULA NAME:")
            if len(name_sections) > 1:
                name_line = name_sections[1].split("\n")[0].strip()
                if name_line:
                    formula_data["name"] = name_line
        
        # Parse description
        description_match = None
        for header in ["DESCRIPTION:", "PRODUCT DESCRIPTION:"]:
            if header in ai_response:
                desc_sections = ai_response.split(header)
                if len(desc_sections) > 1:
                    next_header = desc_sections[1].find("\n-")
                    if next_header > 0:
                        description = desc_sections[1][:next_header].strip()
                    else:
                        description = desc_sections[1].split("\n\n")[0].strip()
                    if description:
                        formula_data["description"] = description
                        break
        
        # Parse ingredients
        ingredient_section = None
        if "INGREDIENTS:" in ai_response:
            sections = ai_response.split("INGREDIENTS:")
            if len(sections) > 1:
                next_section = sections[1].find("\n-")
                if next_section > 0:
                    ingredient_section = sections[1][:next_section].strip()
                else:
                    ingredient_section = sections[1].split("\n\n")[0].strip()
        
        if ingredient_section:
            # Process ingredients
            lines = ingredient_section.split("\n")
            ingredient_order = 1
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith("-"):
                    continue
                
                # Try to extract percentage and name
                parts = line.split("%")
                if len(parts) > 1:
                    try:
                        percentage_str = parts[0].strip().replace(",", ".")
                        percentage = float(percentage_str)
                        name_part = parts[1].strip()
                        
                        # Remove leading dash or bullet if present
                        if name_part.startswith("-") or name_part.startswith("•"):
                            name_part = name_part[1:].strip()
                        
                        # Try to identify ingredient in database
                        # This is simplified - you might need more complex matching
                        ingredient = self.db.query(models.Ingredient).filter(
                            models.Ingredient.name.ilike(f"%{name_part}%")
                        ).first()
                        
                        if ingredient:
                            formula_data["ingredients"].append({
                                "ingredient_id": ingredient.id,
                                "percentage": percentage,
                                "order": ingredient_order
                            })
                            ingredient_order += 1
                    except ValueError:
                        continue
        
        # Parse steps
        steps_section = None
        for header in ["MANUFACTURING STEPS:", "MANUFACTURING PROCESS:", "PROCESS:"]:
            if header in ai_response:
                sections = ai_response.split(header)
                if len(sections) > 1:
                    next_section = sections[1].find("\n-")
                    if next_section > 0:
                        steps_section = sections[1][:next_section].strip()
                    else:
                        steps_section = sections[1].split("\n\n")[0].strip()
                    break
        
        if steps_section:
            # Process steps
            lines = steps_section.split("\n")
            step_order = 1
            current_step = ""
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Check if line starts with a number or common step indicator
                if (line[0].isdigit() and "." in line[:3]) or line.startswith("Step"):
                    # Save previous step if exists
                    if current_step:
                        formula_data["steps"].append({
                            "description": current_step,
                            "order": step_order
                        })
                        step_order += 1
                    
                    # Start new step
                    parts = line.split(".", 1) if "." in line else line.split(":", 1)
                    if len(parts) > 1:
                        current_step = parts[1].strip()
                    else:
                        current_step = line
                else:
                    # Continue previous step
                    if current_step:
                        current_step += " " + line
            
            # Add the last step
            if current_step:
                formula_data["steps"].append({
                    "description": current_step,
                    "order": step_order
                })
        
        # If no ingredients or steps were parsed, fall back to rule-based generation
        if not formula_data["ingredients"] or not formula_data["steps"]:
            # You might want to handle this differently, e.g., by using the rule-based generator
            pass
        
        return formula_data