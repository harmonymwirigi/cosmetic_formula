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
        formula_request: Dict[str, Any],
        user_subscription: models.SubscriptionType,
        user_id: int
    ) -> Dict[str, Any]:
        """
            Generate a formula using OpenAI based on subscription tier and preferences.
            
            Args:
                formula_request: Complete formula generation request with all profile fields
                user_subscription: User's subscription tier
                user_id: User ID to retrieve profile data
                
            Returns:
                Dictionary with formula data
            """
        print(f"Generating formula for user {user_id} with request: {formula_request}")
        # Extract basic information
        product_type = formula_request.get("product_type", "moisturizer")
        valid_product_types = ["serum", "moisturizer", "cleanser", "toner", "mask", "essence"]
        if product_type.lower() not in valid_product_types:
            raise ValueError(f"Invalid product type. Must be one of: {', '.join(valid_product_types)}")
        
        # Extract ingredient preferences
        # Normalize array fields
        for field in ["preferred_ingredients", "avoided_ingredients", "skin_concerns", 
                    "sensitivities", "preferred_textures", "preferred_product_types", 
                    "lifestyle_factors", "sales_channels", "performance_goals", 
                    "desired_certifications"]:
            # Ensure field exists and is a list
            if field in formula_request:
                if not isinstance(formula_request[field], list):
                    # Try to parse JSON string
                    if isinstance(formula_request[field], str):
                        try:
                            formula_request[field] = json.loads(formula_request[field])
                        except json.JSONDecodeError:
                            formula_request[field] = []
                    else:
                        formula_request[field] = []
        
        # Extract ingredient preferences
        preferred_ingredients = formula_request.get("preferred_ingredients", [])
        avoided_ingredients = formula_request.get("avoided_ingredients", [])
        
        # Ensure these are lists
        if not isinstance(preferred_ingredients, list):
            preferred_ingredients = []
        if not isinstance(avoided_ingredients, list):
            avoided_ingredients = []
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
            
        # Add ingredients to avoid from text field
        if formula_request.get("ingredients_to_avoid"):
            additional_avoided = formula_request["ingredients_to_avoid"].split(",")
            avoided_ingredient_names.extend([ing.strip() for ing in additional_avoided])
            
        # Add ingredients to avoid from sensitivities
        if formula_request.get("sensitivities"):
            avoided_ingredient_names.extend(formula_request["sensitivities"])
        
        # Get user profile data
        user_profile = self.db.query(models.UserProfile).filter(
            models.UserProfile.user_id == user_id
        ).first()
        
        # Merge form data with profile data (form data takes precedence)
        profile_data = {}
        if user_profile:
            # Convert all None values to empty objects/lists
            profile_dict = {c.name: getattr(user_profile, c.name) for c in user_profile.__table__.columns 
                           if c.name not in ['id', 'user_id', 'created_at', 'updated_at']}
            
            # Ensure JSON fields are properly parsed
            for key, value in profile_dict.items():
                if value and isinstance(value, str) and key in [
                    'skin_concerns', 'skin_texture', 'preferred_textures',
                    'preferred_product_types', 'lifestyle_factors', 'sensitivities',
                    'sales_channels', 'performance_goals', 'desired_certifications'
                ]:
                    try:
                        profile_dict[key] = json.loads(value)
                    except:
                        profile_dict[key] = []
                        
            profile_data = profile_dict
            
        # Merge form data with profile data (form data takes precedence)
        for key, value in formula_request.items():
            if value is not None and key not in ['product_type', 'formula_name', 
                                                'preferred_ingredients', 'avoided_ingredients']:
                profile_data[key] = value
                
        # Prepare professional data for professional tier users
        professional_data = {}
        if user_subscription == models.SubscriptionType.PROFESSIONAL:
            professional_data = {
                'brand_name': profile_data.get('brand_name', ''),
                'development_stage': profile_data.get('development_stage', ''),
                'product_category': profile_data.get('product_category', ''),
                'target_demographic': profile_data.get('target_demographic', ''),
                'sales_channels': profile_data.get('sales_channels', []),
                'target_texture': profile_data.get('target_texture', ''),
                'performance_goals': profile_data.get('performance_goals', []),
                'desired_certifications': profile_data.get('desired_certifications', []),
                'regulatory_requirements': profile_data.get('regulatory_requirements', ''),
                'restricted_ingredients': profile_data.get('restricted_ingredients', ''),
                'preferred_actives': profile_data.get('preferred_actives', ''),
                'production_scale': profile_data.get('production_scale', ''),
                'price_positioning': profile_data.get('price_positioning', ''),
                'competitor_brands': profile_data.get('competitor_brands', ''),
                'brand_voice': profile_data.get('brand_voice', ''),
                'product_inspirations': profile_data.get('product_inspirations', '')
            }
        
        # Generate the appropriate prompt based on subscription tier and data
        prompt = self._generate_tiered_prompt(
            product_type,
            profile_data.get('skin_concerns', []),
            user_subscription,
            preferred_ingredient_names,
            avoided_ingredient_names,
            profile_data,
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
                max_tokens=2500,
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
                profile_data.get('skin_concerns', []),
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
        profile_data: Dict[str, Any],
        professional_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a tiered prompt based on user subscription level, incorporating all profile data.
        """
        # Ensure skin_concerns is a list of strings
        if not skin_concerns:
            skin_concerns = ["general skincare"]
        
        # Base prompt for all tiers
        base_prompt = f"""
Generate a complete cosmetic formula for a {product_type} that addresses the following skin concerns: {', '.join(skin_concerns)}.
"""

        # Add detailed user profile data for all subscription tiers
        profile_prompt = """
USER PROFILE:
"""
        # Personal Info & Environment
        if profile_data.get('age'):
            profile_prompt += f"Age: {profile_data.get('age')}\n"
            
        if profile_data.get('gender'):
            profile_prompt += f"Gender: {profile_data.get('gender')}\n"
            
        if profile_data.get('is_pregnant') is not None:
            profile_prompt += f"Pregnancy Status: {'Pregnant' if profile_data.get('is_pregnant') else 'Not Pregnant'}\n"
            
        if profile_data.get('fitzpatrick_type'):
            profile_prompt += f"Fitzpatrick Skin Type: {profile_data.get('fitzpatrick_type')}\n"
            
        if profile_data.get('climate'):
            profile_prompt += f"Climate: {profile_data.get('climate')}\n"
        
        # Skin Characteristics
        if profile_data.get('skin_type'):
            profile_prompt += f"Skin Type: {profile_data.get('skin_type')}\n"
            
        if profile_data.get('breakout_frequency'):
            profile_prompt += f"Breakout Frequency: {profile_data.get('breakout_frequency')}\n"
            
        if profile_data.get('skin_texture'):
            textures = profile_data.get('skin_texture', [])
            if isinstance(textures, list) and textures:
                profile_prompt += f"Skin Texture: {', '.join(textures)}\n"
                
        if profile_data.get('skin_redness'):
            profile_prompt += f"Skin Redness: {profile_data.get('skin_redness')}\n"
            
        if profile_data.get('end_of_day_skin_feel'):
            profile_prompt += f"End-of-day Skin Feel: {profile_data.get('end_of_day_skin_feel')}\n"
        
        # Skin Concerns & Preferences
        if profile_data.get('preferred_textures'):
            textures = profile_data.get('preferred_textures', [])
            if isinstance(textures, list) and textures:
                profile_prompt += f"Preferred Product Textures: {', '.join(textures)}\n"
                
        if profile_data.get('preferred_routine_length'):
            profile_prompt += f"Preferred Routine Length: {profile_data.get('preferred_routine_length')}\n"
            
        if profile_data.get('preferred_product_types'):
            types = profile_data.get('preferred_product_types', [])
            if isinstance(types, list) and types:
                profile_prompt += f"Preferred Product Types: {', '.join(types)}\n"
                
        if profile_data.get('lifestyle_factors'):
            factors = profile_data.get('lifestyle_factors', [])
            if isinstance(factors, list) and factors:
                profile_prompt += f"Lifestyle Factors Affecting Skin: {', '.join(factors)}\n"
                
        if profile_data.get('sensitivities'):
            sensitivities = profile_data.get('sensitivities', [])
            if isinstance(sensitivities, list) and sensitivities:
                profile_prompt += f"Sensitivities/Allergies: {', '.join(sensitivities)}\n"
        
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
8. Specific details on how this formula addresses the user's skin concerns and preferences
9. Consideration for the user's skin type, texture, and lifestyle factors
10. Anticipated benefits and results

Format the response as follows:
- FORMULA NAME: [Name]
- DESCRIPTION: [Description]
- INGREDIENTS: [List each ingredient with percentage, INCI name, and phase]
- MANUFACTURING STEPS: [Numbered list of steps]
- BENEFITS & RESULTS: [Description of expected benefits]
- USAGE RECOMMENDATIONS: [How to use the product]
- NOTES: [Any additional notes about stability, storage, etc.]
"""
            return base_prompt + premium_prompt
            
        # Professional tier prompt
        elif user_subscription == models.SubscriptionType.PROFESSIONAL:
            # Prepare professional data fields
            brand_name = professional_data.get('brand_name', 'Not specified')
            development_stage = professional_data.get('development_stage', 'Not specified')
            product_category = professional_data.get('product_category', 'Not specified')
            target_demographic = professional_data.get('target_demographic', 'Not specified')
            
            sales_channels = professional_data.get('sales_channels', [])
            if isinstance(sales_channels, list) and sales_channels:
                sales_channels_str = ', '.join(sales_channels)
            else:
                sales_channels_str = 'Not specified'
                
            target_texture = professional_data.get('target_texture', 'Not specified')
            
            performance_goals = professional_data.get('performance_goals', [])
            if isinstance(performance_goals, list) and performance_goals:
                performance_goals_str = ', '.join(performance_goals)
            else:
                performance_goals_str = 'Not specified'
                
            certifications = professional_data.get('desired_certifications', [])
            if isinstance(certifications, list) and certifications:
                certifications_str = ', '.join(certifications)
            else:
                certifications_str = 'Not specified'
                
            regulatory = professional_data.get('regulatory_requirements', 'Not specified')
            restricted = professional_data.get('restricted_ingredients', 'Not specified')
            preferred_actives = professional_data.get('preferred_actives', 'Not specified')
            production_scale = professional_data.get('production_scale', 'Not specified')
            price_positioning = professional_data.get('price_positioning', 'Not specified')
            competitor_brands = professional_data.get('competitor_brands', 'Not specified')
            brand_voice = professional_data.get('brand_voice', 'Not specified')
            inspirations = professional_data.get('product_inspirations', 'Not specified')
            
            professional_prompt = f"""
This is for a PROFESSIONAL subscription user developing a commercial product.

BRAND & BUSINESS INFORMATION:
- Brand Name: {brand_name}
- Development Stage: {development_stage}
- Product Category: {product_category}
- Target Demographic: {target_demographic}
- Sales Channels: {sales_channels_str}
- Price Positioning: {price_positioning}
- Competitor Brands: {competitor_brands}
- Brand Voice: {brand_voice}
- Product Inspirations: {inspirations}

PRODUCT SPECIFICATIONS:
- Target Texture/Experience: {target_texture}
- Performance Goals: {performance_goals_str}
- Desired Certifications: {certifications_str}
- Regulatory Requirements: {regulatory}
- Restricted Ingredients: {restricted}
- Preferred Active Ingredients: {preferred_actives}
- Production Scale: {production_scale}

Please provide a commercial-grade formulation including:
1. A market-appropriate name for the formula aligned with brand positioning
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
12. Shelf-life expectations and stability considerations

Format the response as follows:
- FORMULA NAME: [Name]
- PRODUCT DESCRIPTION: [Description with key claims]
- TARGET MARKET POSITIONING: [Brief overview of market positioning]
- FORMULA OVERVIEW: [Brief overview of formulation approach]
- INGREDIENTS: [Detailed list with percentages, INCI names, phases, and functions]
- MANUFACTURING PROCESS: [Detailed process with temperatures and equipment]
- ALTERNATIVE INGREDIENTS: [Options for substitutions]
- REGULATORY CONSIDERATIONS: [pH, preservation, stability, claims support]
- PACKAGING & SCALE-UP: [Recommendations for packaging and production]
- TESTING PROTOCOLS: [Suggested tests for quality control]
- MARKETING CLAIMS: [Substantiated claims aligned with brand voice]
- SHELF-LIFE & STABILITY: [Expected shelf-life and stability considerations]
"""
            return base_prompt + professional_prompt
            
        # Free tier (should not be reached with current implementation)
        else:
            basic_prompt = """
Please provide a basic formulation that includes:
1. A simple name for the formula
2. A list of ingredients with approximate percentages
3. Basic manufacturing steps

Format the response as follows:
- FORMULA NAME: [Name]
- INGREDIENTS: [List ingredients with percentages]
- MANUFACTURING STEPS: [Basic steps]
"""
            return base_prompt + basic_prompt
    
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
            "type": product_type.title(),  # Set formula type from product_type
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
            # Log fallback to rule-based generator
            print("OpenAI parsing failed to extract ingredients or steps. Falling back to rule-based generator.")
            
            # Fall back to rule-based generator
            try:
                rule_based_formula = self.rule_based_generator.generate_formula(
                    product_type,
                    [],  # Empty skin concerns, will use defaults
                    models.SubscriptionType.PREMIUM,  # Use premium tier for better quality
                    [],  # No preferred ingredients
                    []   # No avoided ingredients
                )
                
                # Extract the proper attributes from the rule_based_formula
                if hasattr(rule_based_formula, 'ingredients'):
                    # For ingredients, we need to extract the correct fields
                    formula_data["ingredients"] = [
                        {
                            "ingredient_id": ingredient.ingredient_id, 
                            "percentage": ingredient.percentage, 
                            "order": ingredient.order
                        }
                        for ingredient in rule_based_formula.ingredients
                    ]
                
                if hasattr(rule_based_formula, 'steps'):
                    # For steps, we need to extract the correct fields
                    formula_data["steps"] = [
                        {
                            "description": step.description, 
                            "order": step.order
                        }
                        for step in rule_based_formula.steps
                    ]
            except Exception as e:
                # Log the error but continue with whatever we have
                print(f"Error in rule-based fallback: {str(e)}")
                import traceback
                print(traceback.format_exc())
        
        return formula_data