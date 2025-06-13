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
        Generate a complete formulation prompt for BeautyCraft based on questionnaire data and subscription tier.
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

        # Format target user information
        target_user_info = []
        if target_user.get('gender'):
            target_user_info.append(f"Gender: {target_user['gender']}")
        if target_user.get('ageGroup'):
            target_user_info.append(f"Age: {target_user['ageGroup']}")
        if target_user.get('skinHairType'):
            target_user_info.append(f"Skin/Hair Type: {target_user['skinHairType']}")
        if target_user.get('culturalBackground'):
            target_user_info.append(f"Cultural Background: {target_user['culturalBackground']}")
        if target_user.get('concerns'):
            target_user_info.append(f"Concerns: {target_user['concerns']}")
        
        target_user_formatted = "; ".join(target_user_info) if target_user_info else "Not specified"

        prompt = f"""You are an expert cosmetic chemist working inside BeautyCraft, an AI-powered formulation SaaS for DIY formulators, indie beauty brands, and cosmetic labs.

    Based on the following client questionnaire, generate a compliant, professional-grade cosmetic formulation.

    --- 
    🎯 PURPOSE: {purpose}  
    💅 PRODUCT CATEGORY: {product_category}  
    🔬 FORMULA TYPE(S): {', '.join(formula_types)}  
    ✨ PRIMARY GOALS: {', '.join(primary_goals)}  
    👤 TARGET USER: {target_user_formatted}  
    ✅ MUST-HAVE INGREDIENTS: {must_have_ingredients or 'No specific requirements'}  
    🚫 INGREDIENTS TO AVOID: {avoid_ingredients or 'No specific restrictions'}  
    🌿 BRAND VISION: {brand_vision or 'Not specified'}  
    🌸 DESIRED SENSORY EXPERIENCE: {', '.join(desired_experience) if desired_experience else 'No specific preferences'}  
    📦 PACKAGING PREFERENCES: {packaging or 'Not specified'}  
    💸 BUDGET: {budget or 'Not specified'}  
    ⏳ TIMELINE: {timeline or 'Not specified'}  
    📝 ADDITIONAL NOTES: {additional_notes or 'None'}  
    ---  

    Generate a complete, REALISTIC formulation with the following structure:

    1. ✅ *INCI Formula Table* - Create a comprehensive formulation with 10-18 ingredients (depending on product complexity):
    **WATER PHASE (typically 60-80% for serums, 70-85% for lotions):**
    - Base: Distilled Water (largest percentage)
    - Humectants: Glycerin, Hyaluronic Acid, or Sodium PCA
    - Water-soluble actives: Niacinamide, Peptides, etc.
    - Chelating agent: EDTA (0.1%)
    - pH adjusters if needed

    **OIL PHASE (typically 15-25% for serums, 10-20% for lotions):**
    - Emulsifier: Appropriate for product type
    - Emollient oils: 2-3 different oils for texture complexity
    - Oil-soluble actives: Retinol, Vitamin E, etc.
    - Thickening agents if needed

    **COOL DOWN PHASE (typically 5-10%):**
    - Preservative system: Broad-spectrum (0.5-1.0%)
    - Heat-sensitive actives
    - Fragrance/Essential oils (if used, max 1%)
    - Additional functional ingredients

    2. 🌡 *Formulation Notes*:  
    - Ideal pH range (specific numbers, e.g., 5.5-6.5)
    - Solubility notes for each ingredient
    - Processing temperature for each phase
    - Incompatibility warnings
    - Expected texture and viscosity
    - Stability considerations

    3. 📈 *Cost Estimation (raw)*:  
    - Cost per 100g batch and per oz
    - Reference supplier for each ingredient  
    - Total raw material cost breakdown

    4. 📜 *Compliance Review*:  
    - Complete INCI label in descending order
    - EU allergen declarations if applicable
    - Green/natural claims compatibility
    - Regulatory notes for target markets

    5. 💡 *Smart Suggestions*:  
    - Ingredient upgrades (premium alternatives)
    - Optional actives for customization
    - Seasonal variations
    - Performance boosters

    6. 📦 *Packaging Recommendation*:  
    - Optimal container type for stability
    - Biodegradable options
    - Supplier recommendations
    - UV protection considerations

    7. 🛠 *Formulator's Tip*:  
    - Critical processing insight for success
    """

        # Add subscription-specific instructions
        if user_subscription == models.SubscriptionType.PROFESSIONAL:
            prompt += """

    🏢 **PROFESSIONAL TIER REQUIREMENTS:**
    - Generate 15-18 ingredient comprehensive formulations
    - Include regulatory compliance notes for FDA & EU markets
    - Provide detailed stability testing protocols
    - Include manufacturing scale-up considerations (pilot to commercial batch)
    - Add complete batch documentation templates
    - Suggest quality control checkpoints and testing parameters
    - Include microbiology testing recommendations
    - Add raw material specification requirements
    """

        elif user_subscription == models.SubscriptionType.PREMIUM:
            prompt += """

    ⭐ **PREMIUM TIER REQUIREMENTS:**
    - Generate 12-15 ingredient well-rounded formulations
    - Include basic regulatory guidance
    - Provide detailed ingredient sourcing recommendations
    - Add intermediate stability notes and testing
    - Include packaging compatibility considerations
    - Suggest performance testing methods
    """

        else:  # FREE tier
            prompt += """

    🆓 **FREE TIER REQUIREMENTS:**
    - Generate 10-12 ingredient complete but accessible formulations
    - Focus on readily available ingredients
    - Provide clear, step-by-step manufacturing instructions
    - Include basic safety and stability guidelines
    - Keep costs reasonable for hobbyist formulators
    """

        prompt += """

    **IMPORTANT GUIDELINES:**
    - Generate REALISTIC, COMPREHENSIVE formulations with 10-18 ingredients minimum
    - Ensure total ingredient percentages add up to exactly 100%
    - Use correct INCI names for all ingredients
    - Include complete preservative system (primary + secondary preservatives typically 0.8-1.2% total)
    - Add chelating agents (EDTA at 0.1%) for stability
    - Include pH adjusters when needed (Citric Acid, Sodium Hydroxide)
    - Mention specific processing temperatures and phase compatibility
    - Include multiple emollients/oils for complex skin feel (don't use just one oil)
    - Add texture modifiers (thickeners, rheology modifiers) for proper consistency
    - Include functional ingredients: antioxidants, penetration enhancers, etc.
    - Reference realistic suppliers: MakingCosmetics, Lotioncrafter, Essential Wholesale, Bulk Apothecary
    - Consider seasonal stability and climate factors
    - Ensure formulations are manufacturing-feasible at small and large scales
    - For emulsions, include proper emulsifier systems (primary + co-emulsifier)
    - Add sensory modifiers for premium feel (silicones, esters, etc.)

    **MINIMUM INGREDIENT EXPECTATIONS BY PRODUCT TYPE:**
    - Serums: 10-15 ingredients (water, humectants, actives, preservatives, pH adjusters, penetration enhancers)
    - Moisturizers/Creams: 12-18 ingredients (emulsion system, multiple emollients, actives, preservatives, texture modifiers)
    - Cleansers: 8-12 ingredients (surfactants, co-surfactants, conditioning agents, preservatives, pH adjusters)
    - Masks: 10-16 ingredients (base system, actives, texture modifiers, preservatives)

    Format your response clearly with the numbered sections above. Make it professional yet accessible for the target subscription tier."""

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