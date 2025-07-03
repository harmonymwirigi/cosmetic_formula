# backend/app/services/ai_formula.py
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app import models, schemas
from app.utils.subscription_mapper import get_formula_limit, map_to_backend_type
import logging

logger = logging.getLogger(__name__)

class FormulationRules:
    """
    Rules for cosmetic formulations based on product type and properties.
    Updated to include pet care products.
    """
    # Base ingredient categories for different product types - UPDATED WITH PET CARE
    PRODUCT_TYPE_BASES = {
        # Face care
        "serum": {
            "water_phase": (70, 90),
            "oil_phase": (5, 15),
            "actives": (1, 10),
            "preservatives": (0.5, 1.5),
        },
        "cream": {
            "water_phase": (60, 80),
            "oil_phase": (15, 30),
            "actives": (1, 8),
            "preservatives": (0.5, 1.5),
        },
        "cleanser": {
            "water_phase": (50, 70),
            "surfactants": (15, 30),
            "oil_phase": (5, 15),
            "preservatives": (0.5, 1.5),
        },
        "toner": {
            "water_phase": (85, 97),
            "actives": (1, 10),
            "preservatives": (0.5, 1.5),
        },
        "face_mask": {
            "water_phase": (60, 85),
            "actives": (2, 15),
            "clays": (5, 20),
            "preservatives": (0.5, 1.5),
        },
        
        # Hair care
        "shampoo": {
            "water_phase": (60, 75),
            "surfactants": (15, 25),
            "conditioning": (1, 5),
            "preservatives": (0.5, 1.5),
        },
        "conditioner": {
            "water_phase": (70, 85),
            "conditioning": (3, 8),
            "emollients": (2, 8),
            "preservatives": (0.5, 1.5),
        },
        "hair_mask": {
            "water_phase": (50, 70),
            "conditioning": (5, 15),
            "proteins": (2, 8),
            "preservatives": (0.5, 1.5),
        },
        
        # Body care
        "body_lotion": {
            "water_phase": (65, 80),
            "oil_phase": (10, 25),
            "emulsifiers": (2, 6),
            "preservatives": (0.5, 1.5),
        },
        "body_scrub": {
            "oil_phase": (30, 60),
            "exfoliants": (20, 40),
            "emollients": (10, 20),
            "preservatives": (0.5, 1.0),
        },
        
        # Pet care - NEW
        "pet_shampoo": {
            "water_phase": (70, 85),
            "mild_surfactants": (8, 15),  # Gentler than human products
            "conditioning": (1, 3),
            "preservatives": (0.3, 0.8),  # Lower preservative levels
        },
        "pet_conditioner": {
            "water_phase": (75, 90),
            "conditioning": (2, 6),
            "emollients": (1, 5),
            "preservatives": (0.3, 0.8),
        },
        "pet_balm": {
            "oil_phase": (70, 95),  # Mostly oil-based
            "waxes": (5, 15),
            "healing_agents": (2, 8),
            "preservatives": (0, 0.5),  # May be preservative-free
        },
        "anti_itch_spray": {
            "water_phase": (85, 95),
            "soothing_agents": (2, 8),
            "antimicrobials": (0.5, 2),
            "preservatives": (0.3, 0.8),
        },
    }
    
    # Ingredient phase mappings - UPDATED
    INGREDIENT_PHASES = {
        "water_phase": ["Water Phase", "Hydrophilic"],
        "oil_phase": ["Oil Phase", "Lipophilic"],
        "actives": ["Active", "Cool Down Phase"],
        "preservatives": ["Preservative"],
        "surfactants": ["Surfactant"],
        "mild_surfactants": ["Mild Surfactant", "Surfactant"],
        "emulsifiers": ["Emulsifier"],
        "thickeners": ["Thickener"],
        "conditioning": ["Conditioning", "Cationic"],
        "soothing_agents": ["Soothing", "Anti-inflammatory"],
        "healing_agents": ["Healing", "Therapeutic"],
        "antimicrobials": ["Antimicrobial", "Preservative"],
        "clays": ["Clay", "Absorbent"],
        "exfoliants": ["Exfoliant", "Abrasive"],
        "waxes": ["Wax", "Structuring"],
    }
    
    # Ingredient functions - UPDATED WITH PET CARE
    INGREDIENT_FUNCTIONS = {
        "humectant": ["Humectant"],
        "emollient": ["Emollient"],
        "occlusive": ["Occlusive"],
        "antioxidant": ["Antioxidant"],
        "preservative": ["Preservative", "Antimicrobial"],
        "active": ["Active", "Exfoliant", "Brightening"],
        "emulsifier": ["Emulsifier"],
        "thickener": ["Thickener", "Viscosity Modifier"],
        "surfactant": ["Surfactant", "Cleansing Agent"],
        "mild_surfactant": ["Mild Surfactant", "Gentle Cleanser"],
        "pH_adjuster": ["pH Adjuster"],
        "conditioning": ["Conditioning Agent", "Detangling"],
        "soothing": ["Soothing", "Anti-inflammatory", "Calming"],
        "healing": ["Healing", "Therapeutic", "Repair"],
        "antimicrobial": ["Antimicrobial", "Antibacterial"],
        "pet_safe": ["Pet Safe", "Non-toxic"],
    }
    
    # Skin/coat concern mappings - UPDATED WITH PET CARE
    SKIN_CONCERN_INGREDIENTS = {
        # Human skin concerns
        "dryness": [
            {"function": "humectant", "priority": "high"},
            {"function": "emollient", "priority": "high"},
            {"function": "occlusive", "priority": "medium"},
        ],
        "aging": [
            {"function": "antioxidant", "priority": "high"},
            {"function": "active", "priority": "high"},
            {"function": "humectant", "priority": "medium"},
        ],
        "acne": [
            {"function": "active", "priority": "high"},
            {"function": "oil_control", "priority": "high"},
            {"function": "antimicrobial", "priority": "medium"},
        ],
        "sensitivity": [
            {"function": "soothing", "priority": "high"},
            {"function": "barrier_repair", "priority": "high"},
            {"function": "humectant", "priority": "medium"},
        ],
        "hyperpigmentation": [
            {"function": "brightening", "priority": "high"},
            {"function": "exfoliant", "priority": "medium"},
            {"function": "antioxidant", "priority": "medium"},
        ],
        
        # Pet care concerns - NEW
        "itchy_skin": [
            {"function": "soothing", "priority": "high"},
            {"function": "antimicrobial", "priority": "medium"},
            {"function": "healing", "priority": "medium"},
        ],
        "dry_coat": [
            {"function": "emollient", "priority": "high"},
            {"function": "conditioning", "priority": "high"},
            {"function": "humectant", "priority": "medium"},
        ],
        "odor": [
            {"function": "antimicrobial", "priority": "high"},
            {"function": "deodorizing", "priority": "high"},
            {"function": "cleansing", "priority": "medium"},
        ],
        "pest_control": [
            {"function": "repellent", "priority": "high"},
            {"function": "antimicrobial", "priority": "medium"},
            {"function": "soothing", "priority": "low"},
        ],
        "general_pet": [
            {"function": "pet_safe", "priority": "high"},
            {"function": "mild_surfactant", "priority": "medium"},
            {"function": "conditioning", "priority": "medium"},
        ],
    }
    
    # Ingredient compatibility - UPDATED WITH PET RESTRICTIONS
    INCOMPATIBLE_INGREDIENTS = [
        # Human cosmetic incompatibilities
        ("Vitamin C (L-Ascorbic Acid)", "Niacinamide"),
        ("Retinol", "AHA/BHA Acids"),
        ("Retinol", "Benzoyl Peroxide"),
        
        # Pet safety incompatibilities - CRITICAL
        ("Essential Oils", "Pet Products"),  # Many essential oils are toxic to pets
        ("Xylitol", "Pet Products"),  # Toxic to dogs
        ("Tea Tree Oil", "Pet Products"),  # Can be toxic in high concentrations
        ("Parabens", "Pet Products"),  # Avoid for pet safety
        ("Sulfates", "Pet Products"),  # Too harsh for pet skin
        ("Alcohol", "Pet Products"),  # Can be drying and harmful
    ]
    
    # Pet-safe ingredient alternatives - NEW
    PET_SAFE_ALTERNATIVES = {
        "surfactant": ["Cocamidopropyl Betaine", "Coco Glucoside", "Sodium Cocoyl Isethionate"],
        "preservative": ["Potassium Sorbate", "Sodium Benzoate", "Natural Preservative Blend"],
        "conditioning": ["Hydrolyzed Oat Protein", "Panthenol", "Aloe Vera Extract"],
        "soothing": ["Colloidal Oatmeal", "Chamomile Extract", "Calendula Extract"],
        "moisturizing": ["Glycerin", "Aloe Vera", "Coconut Oil", "Shea Butter"],
        "antimicrobial": ["Neem Extract", "Colloidal Silver", "Grapefruit Seed Extract"],
    }

class AIFormulaGenerator:
    """
    AI-powered formula generation service.
    Updated to handle pet care formulations.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.rules = FormulationRules()
    
    def get_available_ingredients(self, user_subscription: models.SubscriptionType) -> Dict[str, List[models.Ingredient]]:
        """
        Get all available ingredients categorized by phase, filtered by user subscription.
        """
        ingredients_by_phase = {}
        
        # Query ingredients based on subscription type
        query = self.db.query(models.Ingredient)
        
        try:
            # Handle different subscription types, including frontend names
            subscription_value = user_subscription
            if hasattr(user_subscription, 'value'):
                subscription_value = user_subscription.value
                
            # Convert to lowercase for case-insensitive comparison
            sub_type = subscription_value.lower() if subscription_value else 'free'
            
            if sub_type in ['free']:
                # Free tier - no premium or professional ingredients
                query = query.filter(
                    models.Ingredient.is_premium.is_(False),
                    models.Ingredient.is_professional.is_(False)
                )
            elif sub_type in ['premium', 'creator']:
                # Premium/Creator tier - no professional ingredients
                query = query.filter(models.Ingredient.is_professional.is_(False))
            # Professional/Pro Lab tier - all ingredients available (no filter)
            
            all_ingredients = query.all()
            
            # Categorize by phase
            for ingredient in all_ingredients:
                phase = ingredient.phase or "Uncategorized"
                if phase not in ingredients_by_phase:
                    ingredients_by_phase[phase] = []
                ingredients_by_phase[phase].append(ingredient)
                
        except Exception as e:
            # Log the error but return empty results to avoid crashing
            logger.error(f"Error filtering ingredients by subscription: {str(e)}")
            
        return ingredients_by_phase
    
    def generate_formula(
        self,
        product_type: str,
        skin_concerns: List[str],
        user_subscription: models.SubscriptionType,
        preferred_ingredients: Optional[List[int]] = None,
        avoided_ingredients: Optional[List[int]] = None
    ) -> schemas.FormulaCreate:
        """
        Generate a formula based on product type, skin concerns, and user preferences.
        Updated to handle pet care products.
        """
        # Normalize inputs
        product_type = product_type.lower()
        
        # Map common variations to our base types
        type_mapping = {
            "moisturizer": "cream",
            "face_mask": "face_mask",
            "leave_in_conditioner": "conditioner",
            "body_butter": "body_lotion",
            "shower_gel": "cleanser",
        }
        
        mapped_type = type_mapping.get(product_type, product_type)
        
        if mapped_type not in self.rules.PRODUCT_TYPE_BASES:
            # Default based on category
            if "pet" in product_type:
                mapped_type = "pet_shampoo"
            elif product_type in ["shampoo", "conditioner", "hair_mask", "hair_oil"]:
                mapped_type = product_type
            elif product_type in ["body_lotion", "body_scrub"]:
                mapped_type = product_type  
            else:
                mapped_type = "serum"  # Default fallback
        
        # Get available ingredients
        ingredients_by_phase = self.get_available_ingredients(user_subscription)
        
        # Get preferred and avoided ingredients
        preferred_ingredients = preferred_ingredients or []
        avoided_ingredients = avoided_ingredients or []
        
        # For pet products, ensure pet safety
        if "pet" in product_type:
            skin_concerns = self._ensure_pet_safety_concerns(skin_concerns)
        
        # Step 1: Select base ingredients based on product type
        base_ingredients = self._select_base_ingredients(
            mapped_type, 
            ingredients_by_phase,
            preferred_ingredients,
            avoided_ingredients
        )
        
        # Step 2: Select active ingredients based on skin concerns
        active_ingredients = self._select_active_ingredients(
            skin_concerns,
            ingredients_by_phase,
            preferred_ingredients,
            avoided_ingredients,
            already_selected=[i.ingredient_id for i in base_ingredients],
            is_pet_product="pet" in product_type
        )
        
        # Step 3: Combine and adjust percentages
        formula_ingredients = self._adjust_percentages(
            base_ingredients + active_ingredients,
            mapped_type
        )
        
        # Step 4: Generate steps
        steps = self._generate_steps(formula_ingredients, mapped_type)
        
        # Create formula
        return schemas.FormulaCreate(
            name=f"AI-Generated {product_type.title()}",
            description=f"A {product_type} formulated for {', '.join(skin_concerns)}",
            type=product_type.title(),
            is_public=False,
            total_weight=100.0,
            ingredients=formula_ingredients,
            steps=steps
        )
    
    def _ensure_pet_safety_concerns(self, concerns: List[str]) -> List[str]:
        """Ensure pet products include general pet safety concerns"""
        pet_safe_concerns = concerns.copy()
        if "general_pet" not in pet_safe_concerns:
            pet_safe_concerns.append("general_pet")
        return pet_safe_concerns
    
    def _select_base_ingredients(
        self,
        product_type: str,
        ingredients_by_phase: Dict[str, List[models.Ingredient]],
        preferred_ingredients: List[int],
        avoided_ingredients: List[int]
    ) -> List[schemas.FormulaIngredientCreate]:
        """
        Select base ingredients for the formula.
        Updated to handle pet care products.
        """
        selected_ingredients = []
        order_counter = 1
        
        # Get base requirements for product type
        base_requirements = self.rules.PRODUCT_TYPE_BASES.get(product_type, {})
        
        # For pet products, add extra safety checks
        is_pet_product = "pet" in product_type
        
        # For each phase needed in the base
        for phase_category, (min_pct, max_pct) in base_requirements.items():
            # Get phases that match this category
            phase_names = self.rules.INGREDIENT_PHASES.get(phase_category, [phase_category])
            
            # Collect all ingredients in these phases
            phase_ingredients = []
            for phase in phase_names:
                if phase in ingredients_by_phase:
                    phase_ingredients.extend(ingredients_by_phase[phase])
            
            # Skip if no ingredients available
            if not phase_ingredients:
                continue
            
            # For pet products, filter for pet-safe ingredients
            if is_pet_product:
                phase_ingredients = self._filter_pet_safe_ingredients(phase_ingredients)
            
            # Prioritize preferred ingredients and filter avoided ones
            phase_ingredients = [
                ing for ing in phase_ingredients 
                if ing.id not in avoided_ingredients
            ]
            
            # Sort by preference
            phase_ingredients.sort(
                key=lambda i: (i.id in preferred_ingredients, -1 if i.id in avoided_ingredients else 0),
                reverse=True
            )
            
            # Select top ingredients from this phase
            selected_count = min(len(phase_ingredients), 2)  # Select up to 2 ingredients per phase
            
            if selected_count == 0:
                continue
            
            # Calculate average percentage for each ingredient in this phase
            avg_pct = (min_pct + max_pct) / 2 / selected_count
            
            for i in range(selected_count):
                selected_ingredients.append(
                    schemas.FormulaIngredientCreate(
                        ingredient_id=phase_ingredients[i].id,
                        percentage=avg_pct,
                        order=order_counter
                    )
                )
                order_counter += 1
        
        return selected_ingredients
    
    def _filter_pet_safe_ingredients(self, ingredients: List[models.Ingredient]) -> List[models.Ingredient]:
        """Filter ingredients to only include pet-safe ones"""
        pet_safe_ingredients = []
        
        # List of ingredients/terms to avoid for pets
        avoid_for_pets = [
            "tea tree", "essential oil", "xylitol", "paraben", "sulfate", 
            "alcohol", "menthol", "camphor", "phenol", "salicylic acid"
        ]
        
        for ingredient in ingredients:
            ingredient_name = ingredient.name.lower()
            inci_name = (ingredient.inci_name or "").lower()
            
            # Check if ingredient contains any pet-unsafe terms
            is_safe = True
            for unsafe_term in avoid_for_pets:
                if unsafe_term in ingredient_name or unsafe_term in inci_name:
                    is_safe = False
                    break
            
            if is_safe:
                pet_safe_ingredients.append(ingredient)
        
        return pet_safe_ingredients
    
    def _select_active_ingredients(
        self,
        skin_concerns: List[str],
        ingredients_by_phase: Dict[str, List[models.Ingredient]],
        preferred_ingredients: List[int],
        avoided_ingredients: List[int],
        already_selected: List[int],
        is_pet_product: bool = False
    ) -> List[schemas.FormulaIngredientCreate]:
        """
        Select active ingredients based on skin concerns.
        Updated to handle pet care concerns.
        """
        selected_ingredients = []
        order_counter = len(already_selected) + 1
        
        # Get active ingredients for the specified skin concerns
        for concern in skin_concerns:
            if concern not in self.rules.SKIN_CONCERN_INGREDIENTS:
                continue
                
            concern_ingredients = self.rules.SKIN_CONCERN_INGREDIENTS[concern]
            
            # For each recommended function for this concern
            for recommendation in concern_ingredients:
                function = recommendation["function"]
                priority = recommendation["priority"]
                
                # Get functions that match this category
                function_names = self.rules.INGREDIENT_FUNCTIONS.get(function, [function])
                
                # Collect all ingredients with these functions
                function_ingredients = []
                for phase, ingredients in ingredients_by_phase.items():
                    for ingredient in ingredients:
                        # Skip if already selected
                        if ingredient.id in already_selected:
                            continue
                            
                        # Skip if avoided
                        if ingredient.id in avoided_ingredients:
                            continue
                        
                        # For pet products, ensure ingredients are pet-safe
                        if is_pet_product:
                            if not self._is_ingredient_pet_safe(ingredient):
                                continue
                        
                        # Check if ingredient has the desired function
                        if ingredient.function and any(f in ingredient.function for f in function_names):
                            function_ingredients.append(ingredient)
                
                # Skip if no ingredients available
                if not function_ingredients:
                    continue
                
                # Prioritize preferred ingredients
                function_ingredients.sort(
                    key=lambda i: i.id in preferred_ingredients,
                    reverse=True
                )
                
                # Select top ingredient from this function
                # High priority gets more percentage, but lower for pet products
                if is_pet_product:
                    pct = 3.0 if priority == "high" else 2.0 if priority == "medium" else 1.0
                else:
                    pct = 5.0 if priority == "high" else 3.0 if priority == "medium" else 1.0
                
                selected_ingredients.append(
                    schemas.FormulaIngredientCreate(
                        ingredient_id=function_ingredients[0].id,
                        percentage=pct,
                        order=order_counter
                    )
                )
                order_counter += 1
                already_selected.append(function_ingredients[0].id)
        
        return selected_ingredients
    
    def _is_ingredient_pet_safe(self, ingredient: models.Ingredient) -> bool:
        """Check if an ingredient is safe for pets"""
        name = ingredient.name.lower()
        inci_name = (ingredient.inci_name or "").lower()
        
        # List of unsafe ingredients for pets
        unsafe_for_pets = [
            "tea tree oil", "eucalyptus", "peppermint oil", "wintergreen",
            "xylitol", "paraben", "sodium lauryl sulfate", "sodium laureth sulfate",
            "alcohol denat", "isopropyl alcohol", "benzyl alcohol",
            "phenol", "salicylic acid", "benzoyl peroxide"
        ]
        
        for unsafe in unsafe_for_pets:
            if unsafe in name or unsafe in inci_name:
                return False
        
        return True
    
    def _adjust_percentages(
        self,
        ingredients: List[schemas.FormulaIngredientCreate],
        product_type: str
    ) -> List[schemas.FormulaIngredientCreate]:
        """
        Adjust ingredient percentages to total 100%.
        """
        # Calculate current total
        total_percentage = sum(ingredient.percentage for ingredient in ingredients)
        
        # If the total isn't 100%, adjust proportionally
        if abs(total_percentage - 100.0) > 0.01:  # Allow for small floating-point errors
            adjustment_factor = 100.0 / total_percentage
            
            for ingredient in ingredients:
                ingredient.percentage = round(ingredient.percentage * adjustment_factor, 1)
        
        return ingredients
    
    def _generate_steps(
        self,
        ingredients: List[schemas.FormulaIngredientCreate],
        product_type: str
    ) -> List[schemas.FormulaStepCreate]:
        """
        Generate manufacturing steps based on ingredients and product type.
        Updated to handle pet care products with special safety considerations.
        """
        steps = []
        step_order = 1
        
        # Get ingredient details for all ingredients
        ingredient_ids = [ingredient.ingredient_id for ingredient in ingredients]
        ingredient_details = {
            i.id: i for i in self.db.query(models.Ingredient).filter(models.Ingredient.id.in_(ingredient_ids)).all()
        }
        
        # Organize ingredients by phase
        phases = {}
        for ingredient in ingredients:
            detail = ingredient_details.get(ingredient.ingredient_id)
            if not detail:
                continue
                
            phase = detail.phase or "Uncategorized"
            
            if phase not in phases:
                phases[phase] = []
                
            phases[phase].append({
                "id": detail.id,
                "name": detail.name,
                "inci_name": detail.inci_name,
                "percentage": ingredient.percentage,
                "function": detail.function
            })
        
        # Check if we have an emulsion (both water and oil phases)
        is_emulsion = "Water Phase" in phases and "Oil Phase" in phases
        
        # Check product type for special handling
        is_pet_product = "pet" in product_type.lower()
        is_cleanser = "shampoo" in product_type.lower() or "cleanser" in product_type.lower()
        is_balm = "balm" in product_type.lower()
        
        # Generate steps based on product type and ingredients
        if is_pet_product:
            # Pet products need extra safety considerations
            steps.append(schemas.FormulaStepCreate(
                description="⚠️ PET SAFETY: Ensure all equipment is thoroughly cleaned and sanitized. Use only pet-safe ingredients. Keep workspace free from harmful substances.",
                order=step_order
            ))
            step_order += 1
        
        if is_balm or (not is_emulsion and "Oil Phase" in phases):
            # Oil-based products (balms, oils)
            oil_ingredients = ", ".join([ing["name"] for ing in phases.get("Oil Phase", [])])
            
            steps.append(schemas.FormulaStepCreate(
                description=f"Heat oil phase ingredients ({oil_ingredients}) to 60-65°C in a double boiler.",
                order=step_order
            ))
            step_order += 1
            
            if "Wax" in phases or any("wax" in ing["name"].lower() for phase_ings in phases.values() for ing in phase_ings):
                steps.append(schemas.FormulaStepCreate(
                    description="Melt waxes completely and stir until homogeneous.",
                    order=step_order
                ))
                step_order += 1
            
            # Cool down phase for oil products
            cool_down_ingredients = []
            if "Cool Down Phase" in phases:
                cool_down_ingredients.extend([ing["name"] for ing in phases["Cool Down Phase"]])
            
            if cool_down_ingredients:
                steps.append(schemas.FormulaStepCreate(
                    description=f"Cool to 40°C and add heat-sensitive ingredients ({', '.join(cool_down_ingredients)}) one by one.",
                    order=step_order
                ))
                step_order += 1
        
        elif is_cleanser:
            # Cleansers (shampoos, face cleansers)
            
            # Water phase
            if "Water Phase" in phases:
                water_ingredients = ", ".join([ing["name"] for ing in phases["Water Phase"]])
                steps.append(schemas.FormulaStepCreate(
                    description=f"In a clean beaker, combine water phase ingredients ({water_ingredients}).",
                    order=step_order
                ))
                step_order += 1
            
            # Surfactants - special handling for pet products
            surfactant_ingredients = []
            for phase_ings in phases.values():
                for ing in phase_ings:
                    if ing.get("function") and ("Surfactant" in ing.get("function") or "Cleansing" in ing.get("function")):
                        surfactant_ingredients.append(ing["name"])
            
            if surfactant_ingredients:
                surfactants_str = ", ".join(surfactant_ingredients)
                if is_pet_product:
                    steps.append(schemas.FormulaStepCreate(
                        description=f"Gently incorporate mild surfactants ({surfactants_str}) to minimize foam generation. Pet products require gentle mixing.",
                        order=step_order
                    ))
                else:
                    steps.append(schemas.FormulaStepCreate(
                        description=f"Add surfactants ({surfactants_str}) and mix gently to avoid excessive foaming.",
                        order=step_order
                    ))
                step_order += 1
            
            # pH adjustment - critical for pet products
            if is_pet_product:
                steps.append(schemas.FormulaStepCreate(
                    description="Adjust pH to 6.5-7.5 (pet skin-friendly range) using citric acid or sodium hydroxide as needed.",
                    order=step_order
                ))
            else:
                steps.append(schemas.FormulaStepCreate(
                    description="Adjust pH to 4.5-5.5 using citric acid or sodium hydroxide as needed.",
                    order=step_order
                ))
            step_order += 1
        
        elif is_emulsion:
            # Emulsion-based products (creams, lotions)
            
            # Water phase
            if "Water Phase" in phases:
                water_ingredients = ", ".join([ing["name"] for ing in phases["Water Phase"]])
                steps.append(schemas.FormulaStepCreate(
                    description=f"Heat water phase ingredients ({water_ingredients}) to 70-75°C.",
                    order=step_order
                ))
                step_order += 1
            
            # Oil phase
            if "Oil Phase" in phases:
                oil_ingredients = ", ".join([ing["name"] for ing in phases["Oil Phase"]])
                steps.append(schemas.FormulaStepCreate(
                    description=f"In a separate container, heat oil phase ingredients ({oil_ingredients}) to 70-75°C.",
                    order=step_order
                ))
                step_order += 1
            
            # Emulsification
            steps.append(schemas.FormulaStepCreate(
                description="Slowly add the oil phase to the water phase while stirring continuously.",
                order=step_order
            ))
            step_order += 1
            
            emulsification_method = "homogenize for 2-3 minutes" if is_pet_product else "homogenize for 3-5 minutes"
            steps.append(schemas.FormulaStepCreate(
                description=f"Use high-shear mixer or homogenizer and {emulsification_method} to ensure proper emulsification.",
                order=step_order
            ))
            step_order += 1
            
            steps.append(schemas.FormulaStepCreate(
                description="Continue mixing while cooling the emulsion to room temperature.",
                order=step_order
            ))
            step_order += 1
        
        # Cool down phase for all products
        cool_down_ingredients = []
        if "Cool Down Phase" in phases:
            cool_down_ingredients.extend([ing["name"] for ing in phases["Cool Down Phase"]])
        
        # Active ingredients
        active_ingredients = []
        if "Active" in phases:
            active_ingredients.extend([ing["name"] for ing in phases["Active"]])
        
        # Add actives and cool down ingredients
        if cool_down_ingredients or active_ingredients:
            ingredients_str = ", ".join(cool_down_ingredients + active_ingredients)
            temp_threshold = "35°C" if is_pet_product else "40°C"
            steps.append(schemas.FormulaStepCreate(
                description=f"Once cooled to below {temp_threshold}, add heat-sensitive ingredients ({ingredients_str}) one by one, mixing gently after each addition.",
                order=step_order
            ))
            step_order += 1
        
        # Preservatives
        preservative_ingredients = []
        for phase_ings in phases.values():
            for ing in phase_ings:
                if ing.get("function") == "Preservative":
                    preservative_ingredients.append(ing["name"])
        
        if preservative_ingredients:
            preservatives_str = ", ".join(preservative_ingredients)
            steps.append(schemas.FormulaStepCreate(
                description=f"Add preservatives ({preservatives_str}) and mix thoroughly to ensure even distribution.",
                order=step_order
            ))
            step_order += 1
        
        # Final pH check
        if not is_balm:  # Skip pH for oil-only products
            ideal_ph = self._get_ideal_ph_range(product_type)
            steps.append(schemas.FormulaStepCreate(
                description=f"Check the final pH and adjust if necessary to {ideal_ph}.",
                order=step_order
            ))
            step_order += 1
        
        # Packaging with pet safety considerations
        if is_pet_product:
            steps.append(schemas.FormulaStepCreate(
                description="Transfer to clean, pet-safe containers. Label clearly with ingredients and usage instructions. Store away from children and pets.",
                order=step_order
            ))
        else:
            container_type = "jars" if "cream" in product_type or "balm" in product_type else "bottles"
            steps.append(schemas.FormulaStepCreate(
                description=f"Transfer to clean {container_type} and store in a cool, dry place away from direct sunlight.",
                order=step_order
            ))
        
        return steps

    def _get_ideal_ph_range(self, product_type: str) -> str:
        """
        Returns the ideal pH range for different product types, including pet care.
        """
        product_type = product_type.lower()
        
        # Pet products have different pH requirements
        if "pet" in product_type:
            if "shampoo" in product_type:
                return "6.5-7.5"  # More neutral for pet skin
            elif "conditioner" in product_type:
                return "6.0-7.0"
            else:
                return "6.5-7.5"  # General pet-safe range
        
        # Human products
        if product_type in ["cleanser", "face wash", "shampoo"]:
            return "4.5-5.5"
        elif product_type in ["toner", "essence"]:
            return "4.0-5.5"
        elif product_type in ["serum"]:
            return "5.0-6.0"
        elif product_type in ["moisturizer", "cream", "lotion", "conditioner"]:
            return "5.0-6.0"
        elif product_type in ["face mask"]:
            return "5.0-7.0"
        else:
            return "5.0-6.0"  # Default pH range for most cosmetic products