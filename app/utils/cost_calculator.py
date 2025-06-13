# backend/app/utils/cost_calculator.py

from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from datetime import datetime
import math
from ..models import Formula, Ingredient, formula_ingredients
from ..schemas import FormulaCostBreakdown, IngredientCostBreakdown, UnitType
from .currency_converter import CurrencyConverter
import logging

logger = logging.getLogger(__name__)

class CostCalculator:
    """
    Comprehensive cost calculation utility for cosmetic formulations
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.currency_converter = CurrencyConverter(db)
    
    # Unit conversion constants (all to grams)
    UNIT_TO_GRAMS = {
        'g': 1.0,
        'gram': 1.0,
        'grams': 1.0,
        'oz': 28.3495,  # 1 ounce = 28.3495 grams
        'ounce': 28.3495,
        'ounces': 28.3495,
        'kg': 1000.0,   # 1 kilogram = 1000 grams
        'kilogram': 1000.0,
        'kilograms': 1000.0,
        'lb': 453.592,  # 1 pound = 453.592 grams
        'pound': 453.592,
        'pounds': 453.592,
        'ml': 1.0,      # Assume 1ml ≈ 1g for cosmetic ingredients (density ≈ 1)
        'milliliter': 1.0,
        'milliliters': 1.0,
        'l': 1000.0,    # 1 liter = 1000ml ≈ 1000g
        'liter': 1000.0,
        'liters': 1000.0,
    }
    
    # Reverse conversion (grams to other units)
    GRAMS_TO_UNIT = {unit: 1.0 / multiplier for unit, multiplier in UNIT_TO_GRAMS.items()}
    
    def convert_to_grams(self, quantity: float, unit: str) -> float:
        """
        Convert any supported unit to grams
        
        Args:
            quantity: Amount in the specified unit
            unit: Unit type (g, oz, kg, lb, ml, l)
            
        Returns:
            Equivalent amount in grams
        """
        unit_lower = unit.lower().strip()
        multiplier = self.UNIT_TO_GRAMS.get(unit_lower, 1.0)
        return quantity * multiplier
    
    def convert_from_grams(self, grams: float, target_unit: str) -> float:
        """
        Convert grams to any supported unit
        
        Args:
            grams: Amount in grams
            target_unit: Target unit type
            
        Returns:
            Equivalent amount in target unit
        """
        unit_lower = target_unit.lower().strip()
        divisor = self.UNIT_TO_GRAMS.get(unit_lower, 1.0)
        return grams / divisor
    
    def calculate_cost_per_gram(self, ingredient: Ingredient) -> Optional[float]:
        """
        Calculate standardized cost per gram for an ingredient
        
        Args:
            ingredient: Ingredient object with cost information
            
        Returns:
            Cost per gram in USD, or None if insufficient data
        """
        try:
            # If cost_per_gram is already calculated and current, use it
            if ingredient.cost_per_gram and ingredient.last_updated_cost:
                # Check if cost was updated recently (within 30 days)
                days_since_update = (datetime.utcnow() - ingredient.last_updated_cost).days
                if days_since_update <= 30:
                    return ingredient.cost_per_gram
            
            # Calculate from purchase data if available
            if (ingredient.purchase_cost and 
                ingredient.purchase_quantity and 
                ingredient.purchase_unit):
                
                # Convert purchase quantity to grams
                quantity_in_grams = self.convert_to_grams(
                    ingredient.purchase_quantity, 
                    ingredient.purchase_unit
                )
                
                # Add shipping cost if applicable
                total_cost = ingredient.purchase_cost
                if ingredient.shipping_cost:
                    total_cost += ingredient.shipping_cost
                
                # Calculate cost per gram in ingredient's currency
                cost_per_gram_local = total_cost / quantity_in_grams
                
                # Convert to USD if needed
                if ingredient.currency and ingredient.currency.upper() != 'USD':
                    # Note: This would need async handling in a real implementation
                    # For now, we'll store the local currency cost and convert when needed
                    return cost_per_gram_local
                else:
                    return cost_per_gram_local
            
            # Fall back to stored cost_per_gram
            return ingredient.cost_per_gram
            
        except Exception as e:
            logger.error(f"Error calculating cost per gram for ingredient {ingredient.id}: {e}")
            return None
    
    async def calculate_cost_per_gram_async(self, ingredient: Ingredient) -> Optional[float]:
        """
        Async version of cost per gram calculation with currency conversion
        """
        try:
            # If cost_per_gram is already calculated and current, use it
            if ingredient.cost_per_gram and ingredient.last_updated_cost:
                days_since_update = (datetime.utcnow() - ingredient.last_updated_cost).days
                if days_since_update <= 30:
                    return ingredient.cost_per_gram
            
            # Calculate from purchase data if available
            if (ingredient.purchase_cost and 
                ingredient.purchase_quantity and 
                ingredient.purchase_unit):
                
                # Convert purchase quantity to grams
                quantity_in_grams = self.convert_to_grams(
                    ingredient.purchase_quantity, 
                    ingredient.purchase_unit
                )
                
                # Add shipping cost if applicable
                total_cost = ingredient.purchase_cost
                if ingredient.shipping_cost:
                    total_cost += ingredient.shipping_cost
                
                # Calculate cost per gram in ingredient's currency
                cost_per_gram_local = total_cost / quantity_in_grams
                
                # Convert to USD if needed
                if ingredient.currency and ingredient.currency.upper() != 'USD':
                    cost_per_gram_usd = await self.currency_converter.convert_amount(
                        cost_per_gram_local, 
                        ingredient.currency, 
                        'USD'
                    )
                    return cost_per_gram_usd
                else:
                    return cost_per_gram_local
            
            return ingredient.cost_per_gram
            
        except Exception as e:
            logger.error(f"Error calculating cost per gram for ingredient {ingredient.id}: {e}")
            return None
    
    def calculate_ingredient_quantity_needed(
        self, 
        percentage: float, 
        batch_size: float, 
        batch_unit: str = 'g'
    ) -> float:
        """
        Calculate how much of an ingredient is needed for a formula
        
        Args:
            percentage: Ingredient percentage in formula (0-100)
            batch_size: Size of the batch to make
            batch_unit: Unit of the batch size
            
        Returns:
            Quantity needed in grams
        """
        # Convert batch size to grams
        batch_size_grams = self.convert_to_grams(batch_size, batch_unit)
        
        # Calculate ingredient quantity needed
        quantity_needed = (percentage / 100.0) * batch_size_grams
        
        return quantity_needed
    
    async def calculate_formula_cost_breakdown(
        self, 
        formula_id: int, 
        batch_size: Optional[float] = None,
        batch_unit: Optional[str] = None,
        target_currency: str = 'USD'
    ) -> FormulaCostBreakdown:
        """
        Calculate complete cost breakdown for a formula
        
        Args:
            formula_id: ID of the formula
            batch_size: Custom batch size (optional, uses formula default)
            batch_unit: Unit for batch size (optional, uses formula default)
            target_currency: Currency for cost display
            
        Returns:
            Complete cost breakdown
        """
        # Get formula with ingredients
        formula = self.db.query(Formula).filter(Formula.id == formula_id).first()
        if not formula:
            raise ValueError(f"Formula with ID {formula_id} not found")
        
        # Use provided batch size or formula default
        if batch_size is None:
            batch_size = formula.batch_size or formula.total_weight or 100.0
        if batch_unit is None:
            batch_unit = formula.batch_unit or 'g'
        
        # Get formula ingredients with their associations
        from sqlalchemy import text
        sql = text("""
            SELECT ingredient_id, percentage, "order" 
            FROM formula_ingredients 
            WHERE formula_id = :formula_id
        """)
        ingredient_associations = self.db.execute(sql, {"formula_id": formula_id}).fetchall()
        
        ingredient_costs = []
        total_batch_cost = 0.0
        missing_cost_ingredients = []
        
        for assoc in ingredient_associations:
            # Get ingredient details
            ingredient = self.db.query(Ingredient).filter(
                Ingredient.id == assoc.ingredient_id
            ).first()
            
            if not ingredient:
                continue
            
            # Calculate quantity needed
            quantity_needed = self.calculate_ingredient_quantity_needed(
                assoc.percentage, batch_size, batch_unit
            )
            
            # Get cost per gram
            cost_per_gram_usd = await self.calculate_cost_per_gram_async(ingredient)
            
            if cost_per_gram_usd is None:
                missing_cost_ingredients.append(ingredient.name)
                cost_per_gram_usd = 0.0
            
            # Calculate total cost for this ingredient
            ingredient_total_cost = quantity_needed * cost_per_gram_usd
            
            # Convert to target currency if needed
            if target_currency != 'USD':
                cost_per_gram_target = await self.currency_converter.convert_amount(
                    cost_per_gram_usd, 'USD', target_currency
                )
                ingredient_total_cost = await self.currency_converter.convert_amount(
                    ingredient_total_cost, 'USD', target_currency
                )
            else:
                cost_per_gram_target = cost_per_gram_usd
            
            # Create ingredient cost breakdown
            ingredient_cost = IngredientCostBreakdown(
                ingredient_id=ingredient.id,
                ingredient_name=ingredient.name,
                percentage=assoc.percentage,
                quantity_needed=quantity_needed,
                quantity_unit='g',
                cost_per_unit=cost_per_gram_target,
                total_cost=ingredient_total_cost,
                currency=target_currency
            )
            
            ingredient_costs.append(ingredient_cost)
            total_batch_cost += ingredient_total_cost
        
        # Convert batch size to grams for calculations
        batch_size_grams = self.convert_to_grams(batch_size, batch_unit)
        
        # Calculate cost per unit of final product
        cost_per_gram = total_batch_cost / batch_size_grams if batch_size_grams > 0 else 0.0
        cost_per_oz = cost_per_gram * 28.3495  # Convert to cost per ounce
        
        return FormulaCostBreakdown(
            formula_id=formula.id,
            formula_name=formula.name,
            batch_size=batch_size,
            batch_unit=batch_unit,
            ingredient_costs=ingredient_costs,
            total_batch_cost=total_batch_cost,
            cost_per_gram=cost_per_gram,
            cost_per_oz=cost_per_oz,
            currency=target_currency,
            calculation_date=datetime.utcnow(),
            missing_cost_ingredients=missing_cost_ingredients
        )
    
    def update_ingredient_cost(
        self, 
        ingredient_id: int, 
        cost_data: Dict
    ) -> bool:
        """
        Update cost information for an ingredient
        
        Args:
            ingredient_id: ID of the ingredient
            cost_data: Dictionary containing cost information
            
        Returns:
            True if successful, False otherwise
        """
        try:
            ingredient = self.db.query(Ingredient).filter(
                Ingredient.id == ingredient_id
            ).first()
            
            if not ingredient:
                return False
            
            # Update cost fields
            for field, value in cost_data.items():
                if hasattr(ingredient, field) and value is not None:
                    setattr(ingredient, field, value)
            
            # Recalculate standardized costs
            if ('purchase_cost' in cost_data or 
                'purchase_quantity' in cost_data or 
                'purchase_unit' in cost_data):
                
                cost_per_gram = self.calculate_cost_per_gram(ingredient)
                if cost_per_gram:
                    ingredient.cost_per_gram = cost_per_gram
                    ingredient.cost_per_oz = cost_per_gram * 28.3495
            
            # Update timestamp
            ingredient.last_updated_cost = datetime.utcnow()
            
            self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error updating ingredient cost: {e}")
            self.db.rollback()
            return False
    
    def get_cost_per_unit_options(self, ingredient: Ingredient) -> Dict[str, float]:
        """
        Get cost per different units for display purposes
        
        Args:
            ingredient: Ingredient object
            
        Returns:
            Dictionary with cost per different units
        """
        cost_per_gram = self.calculate_cost_per_gram(ingredient)
        
        if not cost_per_gram:
            return {}
        
        return {
            'per_gram': cost_per_gram,
            'per_oz': cost_per_gram * 28.3495,
            'per_kg': cost_per_gram * 1000.0,
            'per_lb': cost_per_gram * 453.592,
            'currency': ingredient.currency or 'USD'
        }
    
    def calculate_cost_efficiency_metrics(self, formula_id: int) -> Dict[str, float]:
        """
        Calculate cost efficiency metrics for a formula
        
        Args:
            formula_id: ID of the formula
            
        Returns:
            Dictionary with efficiency metrics
        """
        try:
            # This would need to be async in real implementation
            # For now, returning placeholder structure
            return {
                'cost_per_active_ingredient': 0.0,
                'cost_percentage_actives': 0.0,
                'cost_percentage_base': 0.0,
                'cost_percentage_preservatives': 0.0,
                'most_expensive_ingredient_percentage': 0.0,
                'cheapest_ingredient_percentage': 0.0
            }
        except Exception as e:
            logger.error(f"Error calculating cost efficiency metrics: {e}")
            return {}