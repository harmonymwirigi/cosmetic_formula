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
    These are simplified rules for demonstration purposes.
    """
    # Base ingredient categories for different product types
    PRODUCT_TYPE_BASES = {
        "serum": {
            "water_phase": (70, 90),  # (min_percentage, max_percentage)
            "oil_phase": (5, 15),
            "actives": (1, 10),
            "preservatives": (0.5, 1.5),
        },
        "moisturizer": {
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
    }
    
    # Ingredient phase mappings
    INGREDIENT_PHASES = {
        "water_phase": ["Water Phase", "Hydrophilic"],
        "oil_phase": ["Oil Phase", "Lipophilic"],
        "actives": ["Active", "Cool Down Phase"],
        "preservatives": ["Preservative"],
        "surfactants": ["Surfactant"],
        "emulsifiers": ["Emulsifier"],
        "thickeners": ["Thickener"],
    }
    
    # Ingredient functions
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
        "pH_adjuster": ["pH Adjuster"],
    }
    
    # Skin concern mappings
    SKIN_CONCERN_INGREDIENTS = {
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
    }
    
    # Ingredient compatibility (simplified)
    INCOMPATIBLE_INGREDIENTS = [
        # Pairs of ingredients that shouldn't be used together
        ("Vitamin C (L-Ascorbic Acid)", "Niacinamide"),
        ("Retinol", "AHA/BHA Acids"),
        ("Retinol", "Benzoyl Peroxide"),
    ]

class AIFormulaGenerator:
    """
    AI-powered formula generation service.
    This is a simplified implementation that follows basic formulation rules.
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
        """
        # Normalize inputs
        product_type = product_type.lower()
        if product_type not in self.rules.PRODUCT_TYPE_BASES:
            raise ValueError(f"Unsupported product type: {product_type}")
        
        # Get available ingredients
        ingredients_by_phase = self.get_available_ingredients(user_subscription)
        
        # Get preferred and avoided ingredients
        preferred_ingredients = preferred_ingredients or []
        avoided_ingredients = avoided_ingredients or []
        
        # Step 1: Select base ingredients based on product type
        base_ingredients = self._select_base_ingredients(
            product_type, 
            ingredients_by_phase,
            preferred_ingredients,
            avoided_ingredients
        )
        
        # Step 2: Select active ingredients based on skin concerns
        # CHANGE HERE: Access ingredient_id using dot notation instead of dictionary notation
        active_ingredients = self._select_active_ingredients(
            skin_concerns,
            ingredients_by_phase,
            preferred_ingredients,
            avoided_ingredients,
            already_selected=[i.ingredient_id for i in base_ingredients]  # Changed from i["ingredient_id"]
        )
        
        # Step 3: Combine and adjust percentages
        formula_ingredients = self._adjust_percentages(
            base_ingredients + active_ingredients,
            product_type
        )
        
        # Step 4: Generate steps
        steps = self._generate_steps(formula_ingredients, product_type)
        
        # Create formula
        return schemas.FormulaCreate(
            name=f"AI-Generated {product_type.title()}",
            description=f"A {product_type} formulated for {', '.join(skin_concerns)} skin",
            type=product_type.title(),
            is_public=False,
            total_weight=100.0,
            ingredients=formula_ingredients,
            steps=steps
        )
    
    def _select_base_ingredients(
        self,
        product_type: str,
        ingredients_by_phase: Dict[str, List[models.Ingredient]],
        preferred_ingredients: List[int],
        avoided_ingredients: List[int]
    ) -> List[schemas.FormulaIngredientCreate]:
        """
        Select base ingredients for the formula.
        """
        selected_ingredients = []
        order_counter = 1
        
        # Get base requirements for product type
        base_requirements = self.rules.PRODUCT_TYPE_BASES[product_type]
        
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
            
            # Prioritize preferred ingredients
            phase_ingredients.sort(
                key=lambda i: (i.id in preferred_ingredients, -1 if i.id in avoided_ingredients else 0),
                reverse=True
            )
            
            # Select top ingredients from this phase
            selected_count = min(len(phase_ingredients), 2)  # Select up to 2 ingredients per phase
            
            # Calculate average percentage for each ingredient in this phase
            avg_pct = (min_pct + max_pct) / 2 / selected_count
            
            for i in range(selected_count):
                # Skip avoided ingredients
                if phase_ingredients[i].id in avoided_ingredients:
                    continue
                    
                selected_ingredients.append(
                    schemas.FormulaIngredientCreate(
                        ingredient_id=phase_ingredients[i].id,
                        percentage=avg_pct,
                        order=order_counter
                    )
                )
                order_counter += 1
        
        return selected_ingredients
    
    def _select_active_ingredients(
    self,
    skin_concerns: List[str],
    ingredients_by_phase: Dict[str, List[models.Ingredient]],
    preferred_ingredients: List[int],
    avoided_ingredients: List[int],
    already_selected: List[int]
) -> List[schemas.FormulaIngredientCreate]:
        """
        Select active ingredients based on skin concerns.
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
                # High priority gets more percentage
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
        This enhanced version creates more specific steps based on the actual ingredients selected.
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
        
        # Check if we have special ingredients
        has_actives = "Active" in phases or any(
            ing.get("function") == "Active" for phase_ings in phases.values() for ing in phase_ings
        )
        
        has_preservatives = "Preservative" in phases or any(
            ing.get("function") == "Preservative" for phase_ings in phases.values() for ing in phase_ings
        )
        
        has_thickeners = any(
            ing.get("function") == "Thickener" for phase_ings in phases.values() for ing in phase_ings
        )
        
        has_emulsifiers = any(
            ing.get("function") == "Emulsifier" for phase_ings in phases.values() for ing in phase_ings
        )
        
        # Generate steps based on product type and ingredients
        if product_type.lower() in ["serum", "essence", "toner"]:
            # Water-based products
            
            # Water phase
            if "Water Phase" in phases:
                water_ingredients = ", ".join([ing["name"] for ing in phases["Water Phase"]])
                steps.append(schemas.FormulaStepCreate(
                    description=f"In a clean beaker, combine water phase ingredients ({water_ingredients}).",
                    order=step_order
                ))
                step_order += 1
                
                if has_thickeners:
                    steps.append(schemas.FormulaStepCreate(
                        description="Sprinkle thickeners slowly while mixing to avoid clumping.",
                        order=step_order
                    ))
                    step_order += 1
            
            # Oil phase if present
            if "Oil Phase" in phases:
                oil_ingredients = ", ".join([ing["name"] for ing in phases["Oil Phase"]])
                steps.append(schemas.FormulaStepCreate(
                    description=f"In a separate container, combine oil phase ingredients ({oil_ingredients}).",
                    order=step_order
                ))
                step_order += 1
                
                if is_emulsion:
                    # This is an emulsion requiring both phases
                    steps.append(schemas.FormulaStepCreate(
                        description="Heat both water and oil phases to 70-75°C.",
                        order=step_order
                    ))
                    step_order += 1
                    
                    steps.append(schemas.FormulaStepCreate(
                        description="Slowly add the oil phase to the water phase while stirring continuously.",
                        order=step_order
                    ))
                    step_order += 1
                    
                    steps.append(schemas.FormulaStepCreate(
                        description="Homogenize or use high-shear mixer for 3-5 minutes to ensure proper emulsification.",
                        order=step_order
                    ))
                    step_order += 1
                    
                    steps.append(schemas.FormulaStepCreate(
                        description="Continue stirring while cooling the mixture.",
                        order=step_order
                    ))
                    step_order += 1
            
            # Cool down phase
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
                steps.append(schemas.FormulaStepCreate(
                    description=f"Once cooled to below 40°C, add heat-sensitive ingredients ({ingredients_str}) one by one, mixing gently after each addition.",
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
                    description=f"Add preservatives ({preservatives_str}) and mix thoroughly.",
                    order=step_order
                ))
                step_order += 1
            
            # pH adjustment
            steps.append(schemas.FormulaStepCreate(
                description=f"Check the pH and adjust if necessary to {self._get_ideal_ph_range(product_type)}.",
                order=step_order
            ))
            step_order += 1
            
            # Packaging
            container_type = "dropper bottles" if product_type.lower() == "serum" else "spray bottles" if product_type.lower() == "toner" else "appropriate containers"
            steps.append(schemas.FormulaStepCreate(
                description=f"Transfer to clean {container_type} and store in a cool, dry place.",
                order=step_order
            ))
            
        elif product_type.lower() in ["moisturizer", "lotion", "cream"]:
            # Emulsion-based products
            
            # Water phase
            if "Water Phase" in phases:
                water_ingredients = ", ".join([ing["name"] for ing in phases["Water Phase"]])
                steps.append(schemas.FormulaStepCreate(
                    description=f"In a clean beaker, combine water phase ingredients ({water_ingredients}).",
                    order=step_order
                ))
                step_order += 1
                
                steps.append(schemas.FormulaStepCreate(
                    description="Heat water phase to 70-75°C.",
                    order=step_order
                ))
                step_order += 1
            
            # Oil phase
            if "Oil Phase" in phases:
                oil_ingredients = ", ".join([ing["name"] for ing in phases["Oil Phase"]])
                steps.append(schemas.FormulaStepCreate(
                    description=f"In a separate container, combine oil phase ingredients ({oil_ingredients}).",
                    order=step_order
                ))
                step_order += 1
                
                steps.append(schemas.FormulaStepCreate(
                    description="Heat oil phase to 70-75°C.",
                    order=step_order
                ))
                step_order += 1
            
            # Emulsification
            if is_emulsion:
                steps.append(schemas.FormulaStepCreate(
                    description="Slowly add the oil phase to the water phase while stirring continuously.",
                    order=step_order
                ))
                step_order += 1
                
                steps.append(schemas.FormulaStepCreate(
                    description="Homogenize or use high-shear mixer for 3-5 minutes to ensure proper emulsification.",
                    order=step_order
                ))
                step_order += 1
                
                steps.append(schemas.FormulaStepCreate(
                    description="Continue mixing while cooling the emulsion.",
                    order=step_order
                ))
                step_order += 1
            
            # Cool down phase
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
                steps.append(schemas.FormulaStepCreate(
                    description=f"Once cooled to below 40°C, add heat-sensitive ingredients ({ingredients_str}) one by one, mixing gently after each addition.",
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
                    description=f"Add preservatives ({preservatives_str}) and mix thoroughly.",
                    order=step_order
                ))
                step_order += 1
            
            # pH adjustment
            steps.append(schemas.FormulaStepCreate(
                description=f"Check the pH and adjust if necessary to {self._get_ideal_ph_range(product_type)}.",
                order=step_order
            ))
            step_order += 1
            
            # Packaging
            container_type = "jars" if product_type.lower() in ["cream", "moisturizer"] else "bottles"
            steps.append(schemas.FormulaStepCreate(
                description=f"Transfer to clean {container_type} and store in a cool, dry place.",
                order=step_order
            ))
            
        elif product_type.lower() == "cleanser":
            # Cleansers are usually surfactant-based
            
            # Water phase
            if "Water Phase" in phases:
                water_ingredients = ", ".join([ing["name"] for ing in phases["Water Phase"]])
                steps.append(schemas.FormulaStepCreate(
                    description=f"In a clean beaker, combine water phase ingredients ({water_ingredients}).",
                    order=step_order
                ))
                step_order += 1
            
            # Surfactants
            surfactant_ingredients = []
            for phase_ings in phases.values():
                for ing in phase_ings:
                    if ing.get("function") == "Surfactant":
                        surfactant_ingredients.append(ing["name"])
            
            if surfactant_ingredients:
                surfactants_str = ", ".join(surfactant_ingredients)
                steps.append(schemas.FormulaStepCreate(
                    description=f"In a separate container, gently mix surfactants ({surfactants_str}) to avoid foaming.",
                    order=step_order
                ))
                step_order += 1
                
                steps.append(schemas.FormulaStepCreate(
                    description="Slowly add the surfactant mixture to the water phase while stirring gently.",
                    order=step_order
                ))
                step_order += 1
            
            # Oil phase if present
            if "Oil Phase" in phases:
                oil_ingredients = ", ".join([ing["name"] for ing in phases["Oil Phase"]])
                steps.append(schemas.FormulaStepCreate(
                    description=f"Add oil phase ingredients ({oil_ingredients}) to the mixture.",
                    order=step_order
                ))
                step_order += 1
            
            # Thickeners
            if has_thickeners:
                steps.append(schemas.FormulaStepCreate(
                    description="Sprinkle thickeners slowly while mixing to avoid clumping.",
                    order=step_order
                ))
                step_order += 1
            
            # Actives and cool down ingredients
            cool_down_ingredients = []
            if "Cool Down Phase" in phases:
                cool_down_ingredients.extend([ing["name"] for ing in phases["Cool Down Phase"]])
            
            active_ingredients = []
            if "Active" in phases:
                active_ingredients.extend([ing["name"] for ing in phases["Active"]])
            
            if cool_down_ingredients or active_ingredients:
                ingredients_str = ", ".join(cool_down_ingredients + active_ingredients)
                steps.append(schemas.FormulaStepCreate(
                    description=f"Add heat-sensitive ingredients ({ingredients_str}) and mix gently.",
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
                    description=f"Add preservatives ({preservatives_str}) and mix thoroughly.",
                    order=step_order
                ))
                step_order += 1
            
            # pH adjustment
            steps.append(schemas.FormulaStepCreate(
                description=f"Check the pH and adjust if necessary to {self._get_ideal_ph_range(product_type)}.",
                order=step_order
            ))
            step_order += 1
            
            # Packaging
            steps.append(schemas.FormulaStepCreate(
                description="Transfer to pump bottles or squeeze tubes and store appropriately.",
                order=step_order
            ))
        
        else:
            # Default steps for other product types
            # Water phase
            if "Water Phase" in phases:
                steps.append(schemas.FormulaStepCreate(
                    description="In a clean beaker, combine all water-soluble ingredients.",
                    order=step_order
                ))
                step_order += 1
            
            # Oil phase
            if "Oil Phase" in phases:
                steps.append(schemas.FormulaStepCreate(
                    description="In a separate container, combine all oil-soluble ingredients.",
                    order=step_order
                ))
                step_order += 1
            
            # Combine phases if both present
            if is_emulsion:
                steps.append(schemas.FormulaStepCreate(
                    description="Combine the oil and water phases while mixing thoroughly.",
                    order=step_order
                ))
                step_order += 1
            
            # Add remaining ingredients
            steps.append(schemas.FormulaStepCreate(
                description="Add remaining ingredients one by one, mixing after each addition.",
                order=step_order
            ))
            step_order += 1
            
            # Add preservatives
            if has_preservatives:
                steps.append(schemas.FormulaStepCreate(
                    description="Add preservatives and mix thoroughly.",
                    order=step_order
                ))
                step_order += 1
            
            # Final step
            steps.append(schemas.FormulaStepCreate(
                description="Transfer to appropriate containers and store properly.",
                order=step_order
            ))
        
        return steps

    def _get_ideal_ph_range(self, product_type: str) -> str:
        """
        Returns the ideal pH range for different product types.
        """
        product_type = product_type.lower()
        
        if product_type in ["cleanser", "face wash"]:
            return "4.5-5.5"
        elif product_type in ["toner", "essence"]:
            return "4.0-5.5"
        elif product_type in ["serum"]:
            return "5.0-6.0"
        elif product_type in ["moisturizer", "cream", "lotion"]:
            return "5.0-6.0"
        elif product_type in ["face mask"]:
            return "5.0-7.0"
        else:
            return "5.0-6.0"  # Default pH range for most cosmetic products