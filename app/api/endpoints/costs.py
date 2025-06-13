# backend/app/api/endpoints/costs.py

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import csv
import io
from datetime import datetime

from app import models, schemas, crud
from app.database import get_db
from app.auth import get_current_user
from app.utils.cost_calculator import CostCalculator
from app.utils.currency_converter import CurrencyConverter

router = APIRouter()

@router.post("/ingredients/{ingredient_id}/cost", response_model=schemas.Ingredient)
async def update_ingredient_cost(
    ingredient_id: int,
    cost_data: schemas.IngredientCostUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Update cost information for an ingredient
    """
    # Check if ingredient exists
    ingredient = crud.get_ingredient(db, ingredient_id)
    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingredient not found"
        )
    
    calculator = CostCalculator(db)
    cost_dict = cost_data.dict(exclude_unset=True)
    
    success = calculator.update_ingredient_cost(ingredient_id, cost_dict)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update ingredient cost"
        )
    
    # Return updated ingredient
    updated_ingredient = crud.get_ingredient(db, ingredient_id)
    return updated_ingredient

@router.get("/ingredients/{ingredient_id}/cost", response_model=Dict[str, Any])
async def get_ingredient_cost_breakdown(
    ingredient_id: int,
    target_currency: str = Query("USD", description="Target currency for cost display"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Get detailed cost breakdown for an ingredient
    """
    ingredient = crud.get_ingredient(db, ingredient_id)
    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingredient not found"
        )
    
    calculator = CostCalculator(db)
    cost_options = calculator.get_cost_per_unit_options(ingredient)
    
    # Convert to target currency if needed
    if target_currency != ingredient.currency:
        converter = CurrencyConverter(db)
        # Note: In real implementation, this should be async
        # For now, we'll return the base currency costs
        pass
    
    return {
        "ingredient_id": ingredient.id,
        "ingredient_name": ingredient.name,
        "cost_per_units": cost_options,
        "purchase_info": {
            "purchase_cost": ingredient.purchase_cost,
            "purchase_quantity": ingredient.purchase_quantity,
            "purchase_unit": ingredient.purchase_unit,
            "supplier_name": ingredient.supplier_name,
            "currency": ingredient.currency
        },
        "last_updated": ingredient.last_updated_cost,
        "target_currency": target_currency
    }

@router.post("/formulas/{formula_id}/cost-breakdown", response_model=schemas.FormulaCostBreakdown)
async def calculate_formula_cost_breakdown(
    formula_id: int,
    request: schemas.CostCalculationRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Calculate comprehensive cost breakdown for a formula
    """
    # Verify formula exists and user has access
    formula = crud.get_formula(db, formula_id)
    if not formula:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Formula not found"
        )
    
    if formula.user_id != current_user.id and not formula.is_public:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this formula"
        )
    
    calculator = CostCalculator(db)
    
    try:
        cost_breakdown = await calculator.calculate_formula_cost_breakdown(
            formula_id=formula_id,
            batch_size=request.batch_size,
            batch_unit=request.batch_unit.value if request.batch_unit else None,
            target_currency=request.target_currency
        )
        
        return cost_breakdown
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating cost breakdown: {str(e)}"
        )

@router.post("/formulas/{formula_id}/update-batch-size", response_model=schemas.Formula)
async def update_formula_batch_size(
    formula_id: int,
    batch_size: float,
    batch_unit: schemas.UnitType,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Update the default batch size for a formula
    """
    formula = crud.get_formula(db, formula_id)
    if not formula:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Formula not found"
        )
    
    if formula.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this formula"
        )
    
    # Update batch size
    formula.batch_size = batch_size
    formula.batch_unit = batch_unit.value
    formula.total_weight = batch_size  # Keep in sync for backward compatibility
    
    db.commit()
    db.refresh(formula)
    
    return formula

@router.get("/currencies", response_model=List[schemas.Currency])
async def get_supported_currencies(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Get list of supported currencies with current exchange rates
    """
    currencies = db.query(models.Currency).filter(
        models.Currency.is_active == True
    ).all()
    
    return currencies

@router.post("/currencies/refresh-rates")
async def refresh_exchange_rates(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Manually refresh exchange rates from external API
    """
    converter = CurrencyConverter(db)
    
    try:
        # Get all active currencies
        currencies = db.query(models.Currency).filter(
            models.Currency.is_active == True,
            models.Currency.code != 'USD'  # USD is base currency
        ).all()
        
        updated_count = 0
        for currency in currencies:
            try:
                # Fetch new rate
                new_rate = await converter.get_exchange_rate(currency.code, 'USD')
                currency.exchange_rate_to_usd = new_rate
                currency.last_updated = datetime.utcnow()
                updated_count += 1
            except Exception as e:
                print(f"Failed to update rate for {currency.code}: {e}")
                continue
        
        db.commit()
        
        return {
            "message": f"Successfully updated exchange rates for {updated_count} currencies",
            "updated_count": updated_count
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error refreshing exchange rates: {str(e)}"
        )

@router.post("/ingredients/bulk-cost-import", response_model=schemas.BulkCostImportResult)
async def bulk_import_ingredient_costs(
    file: UploadFile = File(...),
    default_currency: str = Query("USD"),
    supplier_name: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Bulk import ingredient costs from CSV file
    
    Expected CSV format:
    ingredient_name,inci_name,purchase_cost,purchase_quantity,purchase_unit,currency,supplier_name
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV"
        )
    
    try:
        # Read CSV content
        content = await file.read()
        csv_reader = csv.DictReader(io.StringIO(content.decode('utf-8')))
        
        calculator = CostCalculator(db)
        successful_updates = 0
        failed_updates = 0
        errors = []
        updated_ingredients = []
        
        for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 for header
            try:
                # Find ingredient by name or INCI name
                ingredient = db.query(models.Ingredient).filter(
                    (models.Ingredient.name.ilike(f"%{row.get('ingredient_name', '')}%")) |
                    (models.Ingredient.inci_name.ilike(f"%{row.get('inci_name', '')}%"))
                ).first()
                
                if not ingredient:
                    errors.append(f"Row {row_num}: Ingredient '{row.get('ingredient_name')}' not found")
                    failed_updates += 1
                    continue
                
                # Prepare cost data
                cost_data = {
                    'purchase_cost': float(row.get('purchase_cost', 0)) if row.get('purchase_cost') else None,
                    'purchase_quantity': float(row.get('purchase_quantity', 0)) if row.get('purchase_quantity') else None,
                    'purchase_unit': row.get('purchase_unit', 'g').lower(),
                    'currency': row.get('currency', default_currency).upper(),
                    'supplier_name': row.get('supplier_name', supplier_name)
                }
                
                # Remove None values
                cost_data = {k: v for k, v in cost_data.items() if v is not None}
                
                # Update ingredient cost
                success = calculator.update_ingredient_cost(ingredient.id, cost_data)
                
                if success:
                    successful_updates += 1
                    updated_ingredients.append(ingredient.name)
                else:
                    failed_updates += 1
                    errors.append(f"Row {row_num}: Failed to update {ingredient.name}")
                    
            except Exception as e:
                failed_updates += 1
                errors.append(f"Row {row_num}: {str(e)}")
        
        return schemas.BulkCostImportResult(
            total_processed=successful_updates + failed_updates,
            successful_updates=successful_updates,
            failed_updates=failed_updates,
            errors=errors,
            updated_ingredients=updated_ingredients
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing CSV file: {str(e)}"
        )

@router.get("/formulas/{formula_id}/cost-summary", response_model=Dict[str, Any])
async def get_formula_cost_summary(
    formula_id: int,
    target_currency: str = Query("USD"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Get a quick cost summary for a formula (for display in formula cards)
    """
    formula = crud.get_formula(db, formula_id)
    if not formula:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Formula not found"
        )
    
    if formula.user_id != current_user.id and not formula.is_public:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this formula"
        )
    
    calculator = CostCalculator(db)
    
    try:
        # Calculate basic cost info
        cost_breakdown = await calculator.calculate_formula_cost_breakdown(
            formula_id=formula_id,
            target_currency=target_currency
        )
        
        return {
            "formula_id": formula_id,
            "total_batch_cost": cost_breakdown.total_batch_cost,
            "cost_per_gram": cost_breakdown.cost_per_gram,
            "cost_per_oz": cost_breakdown.cost_per_oz,
            "currency": target_currency,
            "batch_size": cost_breakdown.batch_size,
            "batch_unit": cost_breakdown.batch_unit,
            "missing_cost_count": len(cost_breakdown.missing_cost_ingredients),
            "has_complete_cost_data": len(cost_breakdown.missing_cost_ingredients) == 0
        }
        
    except Exception as e:
        return {
            "formula_id": formula_id,
            "total_batch_cost": None,
            "cost_per_gram": None,
            "cost_per_oz": None,
            "currency": target_currency,
            "error": str(e),
            "has_complete_cost_data": False
        }