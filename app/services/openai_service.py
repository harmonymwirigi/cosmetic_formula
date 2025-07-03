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
    Updated to handle pet care and simplified ingredient preferences.
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
        Updated to handle pet care and ensure different formulas based on product type.
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
        
        # Updated valid product types to include pet care
        valid_product_types = [
            # Face care
            "serum", "cream", "cleanser", "toner", "face_mask", "face_oil", "eye_cream", 
            "exfoliant", "essence", "spf_moisturizer", "spot_treatment", "makeup_remover", "facial_mist",
            # Hair care
            "shampoo", "conditioner", "hair_oil", "hair_mask", "leave_in_conditioner", 
            "scalp_scrub", "dry_shampoo", "hair_serum", "hair_gel", "styling_cream", 
            "heat_protectant", "scalp_tonic",
            # Body care
            "body_lotion", "body_butter", "body_scrub", "shower_gel", "bar_soap", 
            "body_oil", "hand_cream", "foot_cream", "deodorant", "body_mist", 
            "stretch_mark_cream", "bust_firming_cream",
            # Pet care - NEW
            "pet_shampoo", "pet_conditioner", "pet_balm", "pet_cologne", "ear_cleaner", 
            "paw_wax", "anti_itch_spray", "flea_tick_spray", "pet_wipes"
        ]
        
        # Map questionnaire types to backend types if needed
        type_mapping = {
            "moisturizer": "cream",
            "toner": "facial_mist",
            "mask": "face_mask",
            "oil": "face_oil",
            "lotion": "body_lotion",
            "leave-in": "leave_in_conditioner",
            "styling": "styling_cream"
        }
        
        product_type = type_mapping.get(primary_formula_type, primary_formula_type)
        if product_type not in valid_product_types:
            # Default based on category
            category_defaults = {
                "face_care": "serum",
                "hair_care": "shampoo", 
                "body_care": "body_lotion",
                "pet_care": "pet_shampoo"
            }
            product_type = category_defaults.get(product_category, "serum")
        
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
                    {"role": "system", "content": "You are an expert cosmetic chemist and product developer specializing in creating personalized skincare, haircare, body care, and pet care formulations."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,  # Higher for more creative names and varied formulas
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
        Generate a complete formulation prompt that ensures different formulas based on product type.
        Updated to handle pet care and simplified additional information field.
        """
        purpose = questionnaire_data.get("purpose", "personal")
        product_category = questionnaire_data.get("product_category", "face_care")
        formula_types = questionnaire_data.get("formula_types", [])
        primary_goals = questionnaire_data.get("primary_goals", [])
        target_user = questionnaire_data.get("target_user", {})
        additional_information = questionnaire_data.get("additional_information", "")  # Simplified field
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

        # Get category-specific details
        category_context = self._get_category_context(product_category, formula_types[0] if formula_types else "")

        prompt = f"""You are an expert cosmetic chemist working inside BeautyCraft, an AI-powered formulation SaaS for DIY formulators, indie beauty brands, and cosmetic labs.

CRITICAL: You MUST create a DIFFERENT and UNIQUE formula for each specific product type. Do NOT generate generic formulas.

Based on the following client questionnaire, generate a compliant, professional-grade cosmetic formulation.

--- 
🎯 PURPOSE: {purpose}  
💅 PRODUCT CATEGORY: {product_category.replace('_', ' ').title()}  
🔬 FORMULA TYPE(S): {', '.join(formula_types)}  
✨ PRIMARY GOALS: {', '.join(primary_goals)}  
👤 TARGET USER: {target_user_formatted}  
📝 ADDITIONAL INFORMATION: {additional_information or 'No specific requirements'}  
🌿 BRAND VISION: {brand_vision or 'Not specified'}  
🌸 DESIRED SENSORY EXPERIENCE: {', '.join(desired_experience) if desired_experience else 'No specific preferences'}  
📦 PACKAGING PREFERENCES: {packaging or 'Not specified'}  
💸 BUDGET: {budget or 'Not specified'}  
⏳ TIMELINE: {timeline or 'Not specified'}  
📝 ADDITIONAL NOTES: {additional_notes or 'None'}  
---  

{category_context}

🧪 **CRITICAL VALIDATION RULES - APPLY BEFORE GENERATING:**

Before generating the formula, apply the following validation rules:

1. **PRODUCT TYPE SPECIFICITY:**
   - {formula_types[0].upper() if formula_types else 'PRODUCT'} formulas are DIFFERENT from other product types
   - Use ingredients and percentages SPECIFIC to {formula_types[0]} formulation
   - Follow industry standards for {formula_types[0]} consistency, texture, and performance
   - Do NOT use generic "one-size-fits-all" formulations

2. **EMULSIFICATION VALIDATION:**
   - If Water Phase > 5% AND Oil Phase > 5% AND no emulsifier is present → MUST add a suitable emulsifier
   - Check emulsifier concentration: typically 2-8% depending on system complexity

3. **GALENIC FORM MATCHING:**
   - **Serums:** Hydrogel or light emulsion based on solubility of actives
   - **Creams/Moisturizers:** REQUIRE emulsifier if water + oil are both > 5%
   - **Oils/Balms:** Anhydrous formulations (no water phase)
   - **Cleansers/Shampoos:** REQUIRE surfactant system + pH 4.5–5.5
   - **Pet Products:** Use pet-safe ingredients only, avoid toxic components

4. **GOAL-SPECIFIC FORMULATION:**
   Based on goals: {', '.join(primary_goals)}, ensure your formula includes:
   {self._get_goal_specific_requirements(primary_goals, product_category)}

5. **AUTOMATIC FIXES REQUIRED:**
   - If formulation violates any rule, FIX IT AUTOMATICALLY and explain the fix
   - Suggest phase adjustments if needed
   - Recommend alternative ingredients if incompatibilities detected

Generate a complete, REALISTIC formulation with the following structure:

**PRODUCT NAME:** Create a unique, creative name that reflects the product type and goals

**DESCRIPTION:** 2-3 sentences describing the product and its key benefits

1. ✅ *INCI Formula Table* - Create a comprehensive formulation with 10-18 ingredients:

**WATER PHASE (adjust based on product type):**
- Base ingredients appropriate for {formula_types[0] if formula_types else 'product'}
- Humectants and water-soluble actives
- Chelating agents (EDTA 0.1%)

**OIL PHASE (adjust based on product type):**
- Emulsifiers (if needed for product type)
- Emollients and oil-soluble actives
- Texture modifiers

**COOL DOWN PHASE:**
- Preservative system (0.8-1.2% total)
- Heat-sensitive actives
- Fragrance (if applicable, max 1%)

2. 🌡 *Formulation Notes*:  
- Ideal pH range for {formula_types[0] if formula_types else 'product'}
- Processing temperatures
- Expected texture and performance
- VALIDATION NOTES: Any automatic fixes applied

3. 📈 *Cost Estimation*:  
- Cost per 100g batch
- Reference suppliers

4. 📜 *Compliance Review*:  
- Complete INCI label in descending order
- Regulatory notes for {product_category}

5. 💡 *Smart Suggestions*:  
- Product-specific performance boosters
- Customization options

6. 📦 *Packaging Recommendation*:  
- Optimal container for {formula_types[0] if formula_types else 'product'}

7. 🛠 *Formulator's Tip*:  
- Critical insight specific to {formula_types[0] if formula_types else 'product'} manufacturing
"""

        # Add subscription-specific instructions
        if user_subscription == models.SubscriptionType.PROFESSIONAL:
            prompt += """

🏢 **PROFESSIONAL TIER REQUIREMENTS:**
- Generate 15-18 ingredient comprehensive formulations
- Include regulatory compliance notes for target markets
- Provide detailed stability testing protocols
- Include manufacturing scale-up considerations
- Add complete batch documentation templates
- Include microbiology testing recommendations
"""

        elif user_subscription == models.SubscriptionType.PREMIUM:
            prompt += """

⭐ **PREMIUM TIER REQUIREMENTS:**
- Generate 12-15 ingredient well-rounded formulations
- Include regulatory guidance
- Provide ingredient sourcing recommendations
- Add stability notes and testing protocols
"""

        else:  # FREE tier
            prompt += """

🆓 **FREE TIER REQUIREMENTS:**
- Generate 10-12 ingredient complete formulations
- Focus on readily available ingredients
- Provide clear manufacturing instructions
- Include basic safety guidelines
"""

        prompt += f"""

**IMPORTANT GUIDELINES:**
- **PRODUCT TYPE SPECIFICITY IS CRITICAL** - Make {formula_types[0] if formula_types else 'this product'} formulas DIFFERENT from others
- Generate REALISTIC formulations with 10-18 ingredients minimum
- Ensure total percentages add up to exactly 100%
- Use correct INCI names for all ingredients
- Include complete preservative system
- Add appropriate texture modifiers for {formula_types[0] if formula_types else 'the product type'}
- Consider the specific goals: {', '.join(primary_goals)}
- Reference realistic suppliers
- Ensure formulations are manufacturing-feasible

**PRODUCT TYPE REQUIREMENTS:**
{self._get_product_type_requirements(formula_types[0] if formula_types else "serum")}

Format your response clearly with the numbered sections above. Make it professional yet accessible."""

        return prompt
    
    def _get_category_context(self, product_category: str, formula_type: str) -> str:
        """Get category-specific context for the prompt"""
        contexts = {
            "face_care": "🌟 **FACE CARE CONTEXT:** Focus on gentle, effective ingredients suitable for facial skin. Consider pH balance, penetration, and compatibility with daily skincare routines.",
            
            "hair_care": "💇‍♀️ **HAIR CARE CONTEXT:** Focus on scalp health, hair shaft conditioning, and cleansing efficacy. Consider hair type variations and styling needs.",
            
            "body_care": "🧴 **BODY CARE CONTEXT:** Focus on larger application areas, longer-lasting effects, and comfort during daily activities. Consider absorption rate and sensory experience.",
            
            "pet_care": "🐕 **PET CARE CONTEXT:** CRITICAL - Use only pet-safe ingredients. Avoid: essential oils toxic to pets, xylitol, parabens, sulfates. Focus on gentle cleansing, coat health, and skin soothing. Consider pet behavior during application."
        }
        return contexts.get(product_category, "")
    
    def _get_goal_specific_requirements(self, goals: List[str], category: str) -> str:
        """Get specific requirements based on goals and category"""
        requirements = []
        
        goal_ingredients = {
            # Face care goals
            "hydrate": "hyaluronic acid, glycerin, ceramides",
            "anti_aging": "retinol alternatives, peptides, antioxidants",
            "anti_acne": "salicylic acid, niacinamide, zinc",
            "soothe": "allantoin, bisabolol, centella asiatica",
            "brighten": "vitamin C, kojic acid, arbutin",
            "exfoliate": "AHA/BHA acids, enzymatic exfoliants",
            
            # Hair care goals  
            "nourish": "proteins, amino acids, natural oils",
            "strengthen": "keratin, biotin, strengthening polymers",
            "hair_growth": "caffeine, rosemary extract, peptides",
            "repair": "ceramides, proteins, reconstructive agents",
            "volume": "volumizing polymers, lightweight oils",
            "moisture": "humectants, emollients, conditioning agents",
            
            # Body care goals
            "moisturize": "shea butter, ceramides, hyaluronic acid", 
            "firm": "caffeine, peptides, firming actives",
            "protect": "antioxidants, UV filters, barrier agents",
            "cleanse": "gentle surfactants, conditioning agents",
            
            # Pet care goals
            "clean": "mild surfactants, natural cleansers",
            "soothe_skin": "oatmeal, aloe vera, chamomile",
            "odor_control": "natural deodorizers, antimicrobials",
            "coat_shine": "natural oils, conditioning agents",
            "anti_itch": "colloidal oatmeal, anti-inflammatory agents",
            "pest_control": "natural repellents (pet-safe only)"
        }
        
        for goal in goals:
            if goal in goal_ingredients:
                requirements.append(f"- {goal.replace('_', ' ').title()}: Include {goal_ingredients[goal]}")
        
        return "\n   ".join(requirements) if requirements else "- Standard formulation for product type"
    
    def _get_product_type_requirements(self, product_type: str) -> str:
        """Get specific requirements for each product type"""
        requirements = {
            # Face Care
            "serum": "Lightweight, fast-absorbing. High active concentration. Minimal emulsifiers. pH 5.0-6.0.",
            "cream": "Rich, moisturizing emulsion. 15-30% oil phase. Multiple emollients. pH 5.0-6.5.",
            "cleanser": "Gentle surfactant system. pH 4.5-5.5. No harsh sulfates for face.",
            "toner": "Water-based. Alcohol-free preferred. pH balancing. Light actives.",
            "face_mask": "Higher active concentration. Clay or hydrogel base. 15-20 minute application.",
            "face_oil": "100% oil phase. Lightweight oils. No water. Essential oil blends.",
            "eye_cream": "Extra gentle. Smaller molecular actives. Rich but non-comedogenic.",
            "exfoliant": "AHA/BHA acids. pH 3.5-4.5. Neutralizing system. Weekly use strength.",
            
            # Hair Care  
            "shampoo": "Cleansing surfactant system. pH 4.5-5.5. Conditioning agents. Scalp-friendly.",
            "conditioner": "Cationic conditioning. pH 4.0-5.0. Detangling properties. No sulfates.",
            "hair_oil": "Lightweight oils. Scalp penetration. No water phase. Natural extracts.",
            "hair_mask": "Deep conditioning. High protein content. 5-20 minute treatment.",
            "leave_in_conditioner": "Light conditioning. Heat protection. Styling benefits.",
            
            # Body Care
            "body_lotion": "Medium viscosity emulsion. Fast absorption. Larger volume application.",
            "body_butter": "Rich, thick texture. High oil content. Long-lasting moisturization.",
            "body_scrub": "Physical exfoliants. Oil base preferred. Gentle on large areas.",
            "shower_gel": "Rich lather. Moisturizing surfactants. pH 5.5-6.5.",
            "body_oil": "Lightweight oils. Fast absorption. Essential oil blends permitted.",
            "deodorant": "Antimicrobial actives. Absorption powders. Fragrance system.",
            
            # Pet Care
            "pet_shampoo": "ULTRA MILD surfactants. pH 6.5-7.5. NO harmful ingredients. Tear-free.",
            "pet_conditioner": "Gentle conditioning. NO silicones. Quick rinse formula.",
            "pet_balm": "Healing ingredients. Lickable formula. NO toxic components.",
            "ear_cleaner": "Gentle cleansing. NO alcohol. Antibacterial properties.",
            "anti_itch_spray": "Soothing actives. NO steroids. Natural anti-inflammatories."
        }
        
        return requirements.get(product_type, "Follow standard cosmetic formulation practices.")
    
    def _parse_questionnaire_response(self, ai_response: str, product_type: str, questionnaire_data: Dict) -> Dict[str, Any]:
        """
        Parse the OpenAI response from questionnaire into structured formula data.
        Enhanced to extract better product names and descriptions.
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
        
        # Parse product name - look for multiple patterns
        name_patterns = ["PRODUCT NAME:", "**PRODUCT NAME:**", "NAME:", "FORMULA NAME:"]
        for pattern in name_patterns:
            if pattern in ai_response:
                name_sections = ai_response.split(pattern)
                if len(name_sections) > 1:
                    name_line = name_sections[1].split("\n")[0].strip()
                    # Clean up the name
                    name_line = name_line.replace("**", "").replace("*", "").replace("[", "").replace("]", "").strip()
                    if name_line and len(name_line) > 3:  # Ensure it's not just punctuation
                        formula_data["name"] = name_line
                        break
        
        # Parse description - look for multiple patterns
        desc_patterns = ["DESCRIPTION:", "**DESCRIPTION:**", "PRODUCT DESCRIPTION:"]
        for pattern in desc_patterns:
            if pattern in ai_response:
                desc_sections = ai_response.split(pattern)
                if len(desc_sections) > 1:
                    # Find the next section header to stop parsing
                    next_headers = ["INGREDIENTS:", "INCI Formula", "FORMULATION:", "WATER PHASE", "1."]
                    next_section = float('inf')
                    for next_header in next_headers:
                        if next_header in desc_sections[1]:
                            next_section = min(next_section, desc_sections[1].find(next_header))
                    
                    if next_section != float('inf'):
                        description = desc_sections[1][:next_section].strip()
                    else:
                        description = desc_sections[1].split("\n\n")[0].strip()
                    
                    # Clean up description
                    description = description.replace("**", "").replace("*", "").strip()
                    if description and len(description) > 10:
                        formula_data["description"] = description
                        break
        
        # If no name found, generate based on type and goals
        if formula_data["name"] == "AI-Generated Formula":
            goals = questionnaire_data.get("primary_goals", [])
            category = questionnaire_data.get("product_category", "")
            
            if goals and category:
                goal_adjectives = {
                    "hydrate": "Hydrating", "anti_aging": "Youth-Boosting", "anti_acne": "Clarifying",
                    "soothe": "Calming", "brighten": "Radiance", "nourish": "Nourishing",
                    "strengthen": "Strengthening", "repair": "Restorative", "clean": "Gentle",
                    "moisturize": "Moisturizing", "firm": "Firming", "protect": "Protective"
                }
                
                primary_goal = goals[0] if goals else "nourishing"
                adjective = goal_adjectives.get(primary_goal, primary_goal.title())
                
                formula_data["name"] = f"{adjective} {product_type.replace('_', ' ').title()}"
        
        # Parse ingredients (existing logic with error handling)
        ingredient_section = None
        ingredient_markers = ["WATER PHASE", "INCI Formula", "INGREDIENTS:", "FORMULATION:"]
        
        for marker in ingredient_markers:
            if marker in ai_response:
                sections = ai_response.split(marker)
                if len(sections) > 1:
                    # Find the next major section
                    next_headers = ["MANUFACTURING", "BENEFITS:", "USAGE:", "MSDS:", "SOP:", "Formulation Notes"]
                    next_section = float('inf')
                    for next_header in next_headers:
                        if next_header in sections[1]:
                            next_section = min(next_section, sections[1].find(next_header))
                    
                    if next_section != float('inf'):
                        ingredient_section = sections[1][:next_section].strip()
                    else:
                        ingredient_section = sections[1].split("\n\n")[0].strip()
                    break
        
        if ingredient_section:
            # Process ingredients with better parsing
            lines = ingredient_section.split("\n")
            ingredient_order = 1
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith("-") or line.startswith("**") or len(line) < 5:
                    continue
                
                # Try to extract percentage and name
                percentage = None
                ingredient_name = None
                inci_name = None
                
                # Pattern: "5% Ingredient Name" or "Ingredient Name - 5%"
                if "%" in line:
                    try:
                        # Multiple patterns to handle different formats
                        if " - " in line and "%" in line.split(" - ")[1]:
                            parts = line.split(" - ")
                            ingredient_name = parts[0].strip()
                            percentage_str = parts[1].strip().replace("%", "").replace(",", ".")
                            percentage = float(percentage_str.split()[0])  # Take first number
                        elif line.strip().endswith("%"):
                            # "Ingredient Name 5%"
                            parts = line.rsplit(" ", 1)
                            if len(parts) == 2:
                                ingredient_name = parts[0].strip()
                                percentage = float(parts[1].replace("%", "").replace(",", "."))
                        else:
                            # "5% Ingredient Name"
                            parts = line.split("%", 1)
                            if len(parts) >= 2:
                                percentage_str = parts[0].strip().replace(",", ".")
                                percentage_str = percentage_str.split()[-1]  # Get last number
                                percentage = float(percentage_str)
                                
                                name_part = parts[1].strip()
                                # Remove leading dash or bullet
                                if name_part.startswith("-") or name_part.startswith("•"):
                                    name_part = name_part[1:].strip()
                                
                                # Extract INCI name from parentheses if available
                                if "(" in name_part and ")" in name_part:
                                    before_paren = name_part.split("(")[0].strip()
                                    inci_match = name_part.split("(")[1].split(")")[0].strip()
                                    ingredient_name = before_paren if before_paren else inci_match
                                    inci_name = inci_match
                                else:
                                    ingredient_name = name_part
                                    inci_name = name_part
                        
                        # Validate parsed data
                        if percentage is not None and ingredient_name and 0 < percentage <= 100:
                            # Create ingredient in database
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
                            
                            self.db.add(new_ingredient)
                            self.db.commit()
                            self.db.refresh(new_ingredient)
                            
                            formula_data["ingredients"].append({
                                "ingredient_id": new_ingredient.id,
                                "percentage": percentage,
                                "order": ingredient_order
                            })
                            ingredient_order += 1
                            
                    except (ValueError, IndexError) as e:
                        print(f"Error parsing ingredient line: {line}. Error: {str(e)}")
                        continue
        
        # Parse manufacturing steps (existing logic)
        steps_patterns = ["MANUFACTURING STEPS:", "MANUFACTURING PROCESS:", "MANUFACTURING:", "PREPARATION:"]
        steps_section = None
        
        for pattern in steps_patterns:
            if pattern in ai_response:
                sections = ai_response.split(pattern)
                if len(sections) > 1:
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
            lines = steps_section.split("\n")
            step_order = 1
            current_step = ""
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Check if line starts with a number or step indicator
                if (line[0].isdigit() and ("." in line[:3] or ":" in line[:3])) or line.startswith("Step"):
                    # Save previous step
                    if current_step:
                        formula_data["steps"].append({
                            "description": current_step.strip(),
                            "order": step_order
                        })
                        step_order += 1
                    
                    # Start new step
                    if "." in line:
                        parts = line.split(".", 1)
                    elif ":" in line:
                        parts = line.split(":", 1)
                    else:
                        parts = [line]
                    
                    current_step = parts[1].strip() if len(parts) > 1 else line
                else:
                    # Continue previous step
                    if current_step:
                        current_step += " " + line
                    else:
                        current_step = line
            
            # Add the last step
            if current_step:
                formula_data["steps"].append({
                    "description": current_step.strip(),
                    "order": step_order
                })
        
        # Generate default MSDS and SOP if not parsed
        if not formula_data.get("msds"):
            formula_data["msds"] = self._generate_default_msds(formula_data["name"])
        
        if not formula_data.get("sop"):
            formula_data["sop"] = self._generate_default_sop(formula_data["name"])
        
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
                "hydrate": "dryness", "anti_aging": "aging", "anti_acne": "acne",
                "soothe": "sensitivity", "brighten": "hyperpigmentation", 
                "balance_oil": "acne", "repair": "aging", "nourish": "dryness",
                "strengthen": "aging", "hair_growth": "aging", "moisturize": "dryness",
                "firm": "aging", "protect": "sensitivity", "cleanse": "general",
                "clean": "general", "soothe_skin": "sensitivity", "odor_control": "general",
                "coat_shine": "general", "anti_itch": "sensitivity", "pest_control": "general"
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
                "hydrate": "Hydrating", "anti_aging": "Anti-Aging", "anti_acne": "Acne-Fighting",
                "soothe": "Soothing", "brighten": "Brightening", "balance_oil": "Oil-Balancing",
                "repair": "Repairing", "nourish": "Nourishing", "strengthen": "Strengthening"
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