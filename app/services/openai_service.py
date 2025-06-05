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
    OpenAI-powered formula generator with questionnaire-based input.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.rule_based_generator = AIFormulaGenerator(db)  # Fallback generator
    
    async def generate_formula_from_questionnaire(
        self,
        questionnaire_data: Dict[str, Any],
        user_subscription: models.SubscriptionType,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Generate a formula using OpenAI based on questionnaire responses.
        
        Args:
            questionnaire_data: Complete questionnaire responses
            user_subscription: User's subscription tier
            user_id: User ID
            
        Returns:
            Dictionary with formula data including AI-generated name
        """
        print(f"Generating formula from questionnaire for user {user_id}")
        
        # Extract and validate questionnaire data
        purpose = questionnaire_data.get("purpose", "personal")
        product_category = questionnaire_data.get("product_category", "face_care")
        formula_types = questionnaire_data.get("formula_types", [])
        primary_goals = questionnaire_data.get("primary_goals", [])
        target_user = questionnaire_data.get("target_user", {})
        
        # Validate required fields
        if not formula_types:
            raise ValueError("At least one formula type must be selected")
        if not primary_goals:
            raise ValueError("At least one primary goal must be selected")
        
        # Determine primary product type for backend compatibility
        primary_formula_type = formula_types[0].lower()
        valid_product_types = ["serum", "moisturizer", "cleanser", "toner", "mask", "essence", "cream", "oil", "lotion"]
        
        # Map questionnaire types to backend types
        type_mapping = {
            "cream": "moisturizer",
            "oil": "serum",
            "lotion": "moisturizer",
            "leave-in / styling": "serum",
            "exfoliator": "cleanser"
        }
        
        product_type = type_mapping.get(primary_formula_type, primary_formula_type)
        if product_type not in valid_product_types:
            product_type = "serum"  # Default fallback
        
        try:
            # Generate the appropriate prompt based on questionnaire responses
            prompt = self._generate_questionnaire_prompt(
                questionnaire_data,
                user_subscription
            )
            
            # Call OpenAI
            response = await openai.ChatCompletion.acreate(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert cosmetic chemist and product developer specializing in creating personalized skincare and haircare formulations."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.6,  # Slightly higher for more creative names
                max_tokens=4000,
                n=1,
                stop=None,
            )
            
            # Process the response
            ai_formula_text = response.choices[0].message.content
            
            # Parse the AI response into formula components
            formula_data = self._parse_questionnaire_response(ai_formula_text, product_type, questionnaire_data)
            return formula_data
            
        except Exception as e:
            print(f"OpenAI API error: {str(e)}")
            # Fall back to rule-based generation with questionnaire data
            return self._generate_fallback_formula(questionnaire_data, user_subscription, product_type)
    
    def _generate_questionnaire_prompt(
        self,
        questionnaire_data: Dict[str, Any],
        user_subscription: models.SubscriptionType
    ) -> str:
        """
        Generate a comprehensive prompt based on questionnaire responses.
        """
        purpose = questionnaire_data.get("purpose", "personal")
        product_category = questionnaire_data.get("product_category", "face_care")
        formula_types = questionnaire_data.get("formula_types", [])
        primary_goals = questionnaire_data.get("primary_goals", [])
        target_user = questionnaire_data.get("target_user", {})
        must_have_ingredients = questionnaire_data.get("preferred_ingredients_text", "")
        avoid_ingredients = questionnaire_data.get("avoided_ingredients_text", "")
        brand_vision = questionnaire_data.get("brand_vision", "")
        desired_experience = questionnaire_data.get("desired_experience", [])
        packaging = questionnaire_data.get("packaging_preferences", "")
        budget = questionnaire_data.get("budget", "")
        timeline = questionnaire_data.get("timeline", "")
        additional_notes = questionnaire_data.get("additional_notes", "")
        
        # Base prompt
        prompt = f"""
Create a complete cosmetic formula based on the following detailed questionnaire responses:

PURPOSE: {purpose}
PRODUCT CATEGORY: {product_category}
FORMULA TYPE(S): {', '.join(formula_types)}
PRIMARY GOALS: {', '.join(primary_goals)}

TARGET USER PROFILE:
- Gender: {target_user.get('gender', 'Not specified')}
- Age Group: {target_user.get('ageGroup', 'Not specified')}
- Skin/Hair Type: {target_user.get('skinHairType', 'Not specified')}
- Cultural Background: {target_user.get('culturalBackground', 'Not specified')}
- Concerns/Lifestyle: {target_user.get('concerns', 'Not specified')}

INGREDIENT PREFERENCES:
- Must Include: {must_have_ingredients if must_have_ingredients else 'No specific requirements'}
- Must Avoid: {avoid_ingredients if avoid_ingredients else 'No specific restrictions'}

DESIRED EXPERIENCE: {', '.join(desired_experience) if desired_experience else 'No specific preferences'}

BRAND VISION: {brand_vision if brand_vision else 'Not specified'}

PACKAGING: {packaging if packaging else 'Not specified'}
BUDGET: {budget if budget else 'Not specified'}
TIMELINE: {timeline if timeline else 'Not specified'}

ADDITIONAL NOTES: {additional_notes if additional_notes else 'None'}
"""

        # Add subscription-specific instructions
        if user_subscription == models.SubscriptionType.PROFESSIONAL:
            prompt += """
This is for a PROFESSIONAL user developing a commercial product. Please provide:

1. A creative, market-ready product name that reflects the brand vision and target market
2. A comprehensive product description with marketing appeal
3. Complete ingredient list with exact percentages (totaling 100%)
4. Detailed manufacturing process with specific temperatures and equipment
5. Marketing positioning and key claims
6. Regulatory considerations and compliance notes
7. Material Safety Data Sheet (MSDS)
8. Standard Operating Procedure (SOP)
9. Packaging recommendations based on formula type
10. Stability and shelf-life considerations

Format the response as follows:
- PRODUCT NAME: [Creative, marketable name]
- PRODUCT DESCRIPTION: [Marketing-focused description]
- TARGET MARKET: [Detailed market analysis]
- KEY CLAIMS: [Substantiated product claims]
- INGREDIENTS: [Detailed list with percentages, INCI names, phases, and functions]
- MANUFACTURING PROCESS: [Step-by-step with temperatures and equipment]
- REGULATORY NOTES: [pH, preservation, stability considerations]
- PACKAGING RECOMMENDATIONS: [Specific packaging suggestions]
- MARKETING POSITIONING: [Brand positioning and messaging]
- MSDS: [Complete Material Safety Data Sheet]
- SOP: [Detailed Standard Operating Procedure]
- STABILITY NOTES: [Expected shelf-life and testing recommendations]
"""
        
        elif user_subscription == models.SubscriptionType.PREMIUM:
            prompt += """
This is for a PREMIUM user. Please provide:

1. An appealing product name that reflects the desired goals and experience
2. A detailed product description
3. Complete ingredient list with percentages (totaling 100%)
4. Step-by-step manufacturing instructions
5. Expected benefits and results
6. Usage recommendations
7. Material Safety Data Sheet (MSDS)
8. Standard Operating Procedure (SOP)

Format the response as follows:
- PRODUCT NAME: [Appealing, descriptive name]
- DESCRIPTION: [Detailed product description]
- INGREDIENTS: [List with percentages, INCI names, and phases]
- MANUFACTURING STEPS: [Numbered manufacturing process]
- BENEFITS: [Expected benefits and results]
- USAGE: [How to use the product]
- MSDS: [Material Safety Data Sheet]
- SOP: [Standard Operating Procedure]
- NOTES: [Additional formulation notes]
"""
        
        else:  # FREE tier
            prompt += """
Please provide:

1. A simple, descriptive product name
2. Basic product description
3. Ingredient list with approximate percentages
4. Simple manufacturing steps
5. Material Safety Data Sheet (MSDS)
6. Standard Operating Procedure (SOP)

Format the response as follows:
- PRODUCT NAME: [Simple name]
- DESCRIPTION: [Basic description]
- INGREDIENTS: [List with percentages]
- MANUFACTURING STEPS: [Basic steps]
- MSDS: [Material Safety Data Sheet]
- SOP: [Standard Operating Procedure]
"""
        
        # Add specific formulation guidelines
        prompt += """

IMPORTANT FORMULATION GUIDELINES:
- All ingredient percentages must total exactly 100%
- Use proper INCI (International Nomenclature of Cosmetic Ingredients) names
- Include appropriate preservation system (0.5-1.5%)
- Consider pH requirements for the product type
- Ensure ingredient compatibility
- Include both common names and INCI names for ingredients
- Provide realistic percentage ranges for each ingredient
- Consider the desired texture and experience in ingredient selection
- Include phase information (water phase, oil phase, cool-down phase)
- Suggest appropriate emulsifiers if creating an emulsion
- Consider the target user's specific needs and restrictions

Please create a formula that truly addresses the user's specific goals and preferences while being safe, stable, and effective.
"""
        
        return prompt
    
    def _parse_questionnaire_response(self, ai_response: str, product_type: str, questionnaire_data: Dict) -> Dict[str, Any]:
        """
        Parse the OpenAI response from questionnaire into structured formula data.
        """
        # Initialize formula data
        formula_data = {
            "name": "AI-Generated Formula",
            "description": "",
            "type": product_type.title(),
            "ingredients": [],
            "steps": [],
            "msds": "",
            "sop": "",
            "benefits": "",
            "usage": "",
            "marketing_claims": "",
            "regulatory_notes": ""
        }
        
        # Parse product name - this is the key improvement
        if "PRODUCT NAME:" in ai_response:
            name_sections = ai_response.split("PRODUCT NAME:")
            if len(name_sections) > 1:
                name_line = name_sections[1].split("\n")[0].strip()
                if name_line:
                    # Clean up the name (remove brackets, extra punctuation)
                    name_line = name_line.replace("[", "").replace("]", "").strip()
                    formula_data["name"] = name_line
        
        # Parse description
        for header in ["DESCRIPTION:", "PRODUCT DESCRIPTION:"]:
            if header in ai_response:
                desc_sections = ai_response.split(header)
                if len(desc_sections) > 1:
                    # Find the next section header to stop parsing
                    next_headers = ["INGREDIENTS:", "TARGET MARKET:", "KEY CLAIMS:", "MANUFACTURING"]
                    next_section = float('inf')
                    for next_header in next_headers:
                        if next_header in desc_sections[1]:
                            next_section = min(next_section, desc_sections[1].find(next_header))
                    
                    if next_section != float('inf'):
                        description = desc_sections[1][:next_section].strip()
                    else:
                        description = desc_sections[1].split("\n\n")[0].strip()
                    
                    if description:
                        formula_data["description"] = description
                        break
        
        # Parse benefits
        if "BENEFITS:" in ai_response:
            benefits_sections = ai_response.split("BENEFITS:")
            if len(benefits_sections) > 1:
                next_section = benefits_sections[1].find("\n-")
                if next_section > 0:
                    benefits = benefits_sections[1][:next_section].strip()
                else:
                    benefits = benefits_sections[1].split("\n\n")[0].strip()
                if benefits:
                    formula_data["benefits"] = benefits
        
        # Parse usage instructions
        if "USAGE:" in ai_response:
            usage_sections = ai_response.split("USAGE:")
            if len(usage_sections) > 1:
                next_section = usage_sections[1].find("\n-")
                if next_section > 0:
                    usage = usage_sections[1][:next_section].strip()
                else:
                    usage = usage_sections[1].split("\n\n")[0].strip()
                if usage:
                    formula_data["usage"] = usage
        
        # Parse marketing claims for professional users
        if "KEY CLAIMS:" in ai_response or "MARKETING POSITIONING:" in ai_response:
            header = "KEY CLAIMS:" if "KEY CLAIMS:" in ai_response else "MARKETING POSITIONING:"
            claims_sections = ai_response.split(header)
            if len(claims_sections) > 1:
                next_section = claims_sections[1].find("\n-")
                if next_section > 0:
                    claims = claims_sections[1][:next_section].strip()
                else:
                    claims = claims_sections[1].split("\n\n")[0].strip()
                if claims:
                    formula_data["marketing_claims"] = claims
        
        # Parse MSDS content
        if "MSDS:" in ai_response:
            msds_sections = ai_response.split("MSDS:")
            if len(msds_sections) > 1:
                next_headers = ["SOP:", "NOTES:", "STABILITY"]
                next_section = float('inf')
                for next_header in next_headers:
                    if next_header in msds_sections[1]:
                        next_section = min(next_section, msds_sections[1].find(next_header))
                
                if next_section != float('inf'):
                    msds_content = msds_sections[1][:next_section].strip()
                else:
                    msds_content = msds_sections[1].strip()
                
                formula_data["msds"] = msds_content
        
        # Parse SOP content
        if "SOP:" in ai_response:
            sop_sections = ai_response.split("SOP:")
            if len(sop_sections) > 1:
                next_headers = ["NOTES:", "STABILITY"]
                next_section = float('inf')
                for next_header in next_headers:
                    if next_header in sop_sections[1]:
                        next_section = min(next_section, sop_sections[1].find(next_header))
                
                if next_section != float('inf'):
                    sop_content = sop_sections[1][:next_section].strip()
                else:
                    sop_content = sop_sections[1].strip()
                
                formula_data["sop"] = sop_content
        
        # Parse ingredients
        ingredient_section = None
        if "INGREDIENTS:" in ai_response:
            sections = ai_response.split("INGREDIENTS:")
            if len(sections) > 1:
                # Find the next major section
                next_headers = ["MANUFACTURING", "BENEFITS:", "USAGE:", "MSDS:", "SOP:"]
                next_section = float('inf')
                for next_header in next_headers:
                    if next_header in sections[1]:
                        next_section = min(next_section, sections[1].find(next_header))
                
                if next_section != float('inf'):
                    ingredient_section = sections[1][:next_section].strip()
                else:
                    ingredient_section = sections[1].split("\n\n")[0].strip()
        
        if ingredient_section:
            # Process ingredients
            lines = ingredient_section.split("\n")
            ingredient_order = 1
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith("-") or line.startswith("INGREDIENTS"):
                    continue
                
                # Try to extract percentage and name
                # Look for patterns like "5% Niacinamide" or "Niacinamide - 5%"
                percentage = None
                ingredient_name = None
                inci_name = None
                
                # Pattern 1: "5% Ingredient Name"
                if "%" in line:
                    parts = line.split("%")
                    if len(parts) >= 2:
                        try:
                            # Extract percentage
                            percentage_str = parts[0].strip().replace(",", ".")
                            # Handle cases like "- 5" or "5"
                            percentage_str = percentage_str.split()[-1]
                            percentage = float(percentage_str)
                            
                            # Extract name
                            name_part = parts[1].strip()
                            
                            # Remove leading dash or bullet if present
                            if name_part.startswith("-") or name_part.startswith("•"):
                                name_part = name_part[1:].strip()
                            
                            # Extract INCI name from parentheses if available
                            if "(" in name_part and ")" in name_part:
                                # Split on first parenthesis
                                before_paren = name_part.split("(")[0].strip()
                                inci_match = name_part.split("(")[1].split(")")[0].strip()
                                
                                ingredient_name = before_paren if before_paren else inci_match
                                inci_name = inci_match
                            else:
                                ingredient_name = name_part
                                inci_name = name_part
                            
                        except (ValueError, IndexError) as e:
                            print(f"Error parsing ingredient line: {line}. Error: {str(e)}")
                            continue
                
                # Only proceed if we successfully parsed the ingredient
                if percentage is not None and ingredient_name:
                    try:
                        # Create a new ingredient in the database
                        new_ingredient = models.Ingredient(
                            name=ingredient_name,
                            inci_name=inci_name or ingredient_name,
                            description=f"AI-generated ingredient for {questionnaire_data.get('product_category', 'cosmetic')} product",
                            phase="AI Generated",
                            recommended_max_percentage=percentage * 1.2,
                            function="AI Generated",
                            is_premium=False,
                            is_professional=False
                        )
                        
                        # Add to database
                        self.db.add(new_ingredient)
                        self.db.commit()
                        self.db.refresh(new_ingredient)
                        
                        # Add to formula
                        formula_data["ingredients"].append({
                            "ingredient_id": new_ingredient.id,
                            "percentage": percentage,
                            "order": ingredient_order
                        })
                        ingredient_order += 1
                        
                    except Exception as e:
                        print(f"Error creating ingredient {ingredient_name}: {str(e)}")
                        continue
        
        # Parse manufacturing steps
        steps_section = None
        for header in ["MANUFACTURING STEPS:", "MANUFACTURING PROCESS:", "MANUFACTURING:"]:
            if header in ai_response:
                sections = ai_response.split(header)
                if len(sections) > 1:
                    # Find the next major section
                    next_headers = ["BENEFITS:", "USAGE:", "MSDS:", "SOP:", "NOTES:", "REGULATORY"]
                    next_section = float('inf')
                    for next_header in next_headers:
                        if next_header in sections[1]:
                            next_section = min(next_section, sections[1].find(next_header))
                    
                    if next_section != float('inf'):
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
                if (line[0].isdigit() and ("." in line[:3] or ":" in line[:3])) or line.startswith("Step"):
                    # Save previous step if exists
                    if current_step:
                        formula_data["steps"].append({
                            "description": current_step,
                            "order": step_order
                        })
                        step_order += 1
                    
                    # Start new step - remove step number/indicator
                    if "." in line:
                        parts = line.split(".", 1)
                    elif ":" in line:
                        parts = line.split(":", 1)
                    else:
                        parts = [line]
                    
                    if len(parts) > 1:
                        current_step = parts[1].strip()
                    else:
                        current_step = line
                else:
                    # Continue previous step
                    if current_step:
                        current_step += " " + line
                    else:
                        # Start new step if we don't have one
                        current_step = line
            
            # Add the last step
            if current_step:
                formula_data["steps"].append({
                    "description": current_step,
                    "order": step_order
                })
        
        # If no ingredients or steps were parsed, fall back to rule-based generation
        if not formula_data["ingredients"] or not formula_data["steps"]:
            print("OpenAI parsing failed. Falling back to rule-based generator.")
            return self._generate_fallback_formula(questionnaire_data, models.SubscriptionType.PREMIUM, product_type)
        
        return formula_data
    
    def _generate_fallback_formula(self, questionnaire_data: Dict[str, Any], user_subscription: models.SubscriptionType, product_type: str) -> Dict[str, Any]:
        """
        Generate a fallback formula using rule-based generation when OpenAI fails.
        """
        try:
            # Map questionnaire goals to skin concerns
            goals_to_concerns = {
                "hydrate": "dryness",
                "anti_aging": "aging",
                "anti_acne": "acne",
                "soothe": "sensitivity",
                "brighten": "hyperpigmentation",
                "balance_oil": "acne",
                "repair": "aging"
            }
            
            primary_goals = questionnaire_data.get("primary_goals", [])
            skin_concerns = [goals_to_concerns.get(goal, "general") for goal in primary_goals if goal in goals_to_concerns]
            
            if not skin_concerns:
                skin_concerns = ["general"]
            
            # Generate using rule-based generator
            rule_based_formula = self.rule_based_generator.generate_formula(
                product_type,
                skin_concerns,
                user_subscription,
                [],  # No specific preferred ingredients
                []   # No specific avoided ingredients
            )
            
            # Generate a name based on questionnaire data
            formula_types = questionnaire_data.get("formula_types", [product_type])
            primary_type = formula_types[0] if formula_types else product_type
            
            # Create a descriptive name
            goal_names = {
                "hydrate": "Hydrating",
                "anti_aging": "Anti-Aging",
                "anti_acne": "Acne-Fighting",
                "soothe": "Soothing",
                "brighten": "Brightening",
                "balance_oil": "Oil-Balancing",
                "repair": "Repairing",
                "nourish": "Nourishing",
                "strengthen": "Strengthening"
            }
            
            goal_descriptors = [goal_names.get(goal, goal.title()) for goal in primary_goals[:2]]
            name_parts = goal_descriptors + [primary_type.title()]
            generated_name = " ".join(name_parts)
            
            # Convert to dictionary format
            formula_data = {
                "name": generated_name,
                "description": rule_based_formula.description,
                "type": rule_based_formula.type,
                "ingredients": [
                    {
                        "ingredient_id": ingredient.ingredient_id,
                        "percentage": ingredient.percentage,
                        "order": ingredient.order
                    }
                    for ingredient in rule_based_formula.ingredients
                ],
                "steps": [
                    {
                        "description": step.description,
                        "order": step.order
                    }
                    for step in rule_based_formula.steps
                ],
                "msds": self._generate_default_msds(generated_name),
                "sop": self._generate_default_sop(generated_name)
            }
            
            return formula_data
            
        except Exception as e:
            print(f"Error in fallback generation: {str(e)}")
            raise ValueError("Failed to generate formula. Please try again.")
    
    def _generate_default_msds(self, formula_name: str) -> str:
        """Generate a default MSDS document."""
        return f"""# Material Safety Data Sheet for {formula_name}

## 1. Product and Company Identification
Product Name: {formula_name}
Product Type: Cosmetic Formulation
Recommended Use: Personal Care

## 2. Hazards Identification
This is a personal care product that is safe for consumers when used according to the label directions.

## 3. Composition/Information on Ingredients
Mixture of cosmetic ingredients. See formula ingredient list for details.

## 4. First Aid Measures
Eye Contact: Flush with water. Seek medical attention if irritation persists.
Skin Contact: Discontinue use if irritation occurs. Wash with water.
Ingestion: Contact a physician or poison control center.

## 5. Handling and Storage
Store in a cool, dry place away from direct sunlight.
Keep out of reach of children.

## 6. Disposal Considerations
Dispose of in accordance with local regulations."""
    
    def _generate_default_sop(self, formula_name: str) -> str:
        """Generate a default SOP document."""
        return f"""# Standard Operating Procedure for {formula_name}

## 1. Equipment and Materials
- Digital scale (precision 0.1g)
- Water bath or double boiler
- Thermometer (0-100°C)
- Glass beakers (various sizes)
- Overhead stirrer or homogenizer
- pH meter
- Clean spatulas and utensils
- Sterilized packaging containers

## 2. Sanitation Procedures
- Sanitize all equipment with 70% isopropyl alcohol
- Ensure clean workspace and wear appropriate PPE
- Use purified water for all formulation steps

## 3. Manufacturing Process
Follow the manufacturing steps provided in the formula details.

## 4. Quality Control
- Check appearance, color, and odor
- Verify pH is appropriate for product type
- Perform stability testing at various temperatures
- Check viscosity and texture

## 5. Packaging and Storage
- Fill containers at appropriate temperature
- Seal containers immediately after filling
- Store in cool, dry place away from direct sunlight
- Label with batch number and production date

## 6. Troubleshooting
- If separation occurs: Check emulsifier percentage and mixing process
- If viscosity issues: Adjust thickener concentration
- If preservation issues: Check pH and preservative system"""