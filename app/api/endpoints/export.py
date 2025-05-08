# backend/app/api/endpoints/export.py - Final solution with landscape mode and special paragraph handling

from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from fastapi.responses import StreamingResponse
import io
import csv
import json
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from app import crud, models, schemas
from app.database import get_db
from app.auth import get_current_user
from sqlalchemy.orm import Session
import logging

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/{formula_id}/export")
async def export_formula(
    formula_id: int,
    format: str = Query(..., description="Export format: pdf, csv, json, or print"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Export a formula in various formats (PDF, CSV, JSON or print-friendly HTML)
    """
    logger.info(f"Export request received for formula {formula_id} in {format} format")
    
    # Get the formula
    formula = crud.get_formula(db, formula_id)
    
    # Check if formula exists and user has access
    if not formula:
        raise HTTPException(status_code=404, detail="Formula not found")
    
    if formula.user_id != current_user.id and not formula.is_public:
        raise HTTPException(status_code=403, detail="Not authorized to access this formula")
    
    # Get user information
    user = db.query(models.User).filter(models.User.id == formula.user_id).first()
    
    # Get ingredients from the formula_ingredients table
    from sqlalchemy import text
    sql = text(f"SELECT ingredient_id, percentage, \"order\" FROM formula_ingredients WHERE formula_id = :formula_id ORDER BY \"order\"")
    ingredients_assoc = db.execute(sql, {"formula_id": formula.id}).fetchall()
    
    # Get ingredient details for each association
    ingredients_data = []
    for assoc in ingredients_assoc:
        ingredient = db.query(models.Ingredient).filter(models.Ingredient.id == assoc.ingredient_id).first()
        if ingredient:
            ingredients_data.append({
                "ingredient_id": assoc.ingredient_id,
                "name": ingredient.name,
                "inci_name": ingredient.inci_name,
                "percentage": assoc.percentage,
                "phase": ingredient.phase or "Uncategorized",
                "function": ingredient.function,
                "order": assoc.order
            })
    
    # Group ingredients by phase
    ingredients_by_phase = {}
    for item in ingredients_data:
        phase = item["phase"]
        if phase not in ingredients_by_phase:
            ingredients_by_phase[phase] = []
        ingredients_by_phase[phase].append(item)
    
    # Sort steps by order
    steps = sorted(formula.steps, key=lambda x: x.order)
    
    # Calculate total percentage
    total_percentage = sum(item["percentage"] for item in ingredients_data)
    
    # Export according to the requested format
    if format.lower() == "pdf":
        # Create PDF
        buffer = io.BytesIO()
        # Use landscape orientation for wider tables
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=landscape(letter),
            rightMargin=0.5*inch, 
            leftMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch
        )
        styles = getSampleStyleSheet()
        
        # Add custom style for header
        styles.add(ParagraphStyle(name='Header', 
                                  parent=styles['Heading1'], 
                                  fontSize=16,
                                  spaceAfter=12))
        
        # Add custom style for subheader
        styles.add(ParagraphStyle(name='SubHeader', 
                                  parent=styles['Heading2'], 
                                  fontSize=14,
                                  spaceAfter=10))
                                  
        # Add custom style for INCI names
        styles.add(ParagraphStyle(
            name='INCI',
            parent=styles['Normal'],
            fontSize=10,
            wordWrap='CJK',  # More aggressive word wrapping
            leading=12,      # Line spacing
            alignment=0      # Left alignment
        ))
        
        # Content elements
        elements = []
        
        # Title
        elements.append(Paragraph(f"Formula: {formula.name}", styles['Header']))
        elements.append(Spacer(1, 0.2*inch))
        
        # Basic Information
        elements.append(Paragraph("Basic Information", styles['SubHeader']))
        basic_info = [
            ["Type", formula.type],
            ["Total Weight", f"{formula.total_weight}g"],
            ["Created By", f"{user.first_name} {user.last_name}"],
            ["Created Date", formula.created_at.strftime("%Y-%m-%d")]
        ]
        
        if formula.description:
            basic_info.append(["Description", formula.description])
        
        # Create basic info table
        basic_info_table = Table(basic_info, colWidths=[2*inch, 6*inch])
        basic_info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (1, 0), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(basic_info_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Ingredients Section
        elements.append(Paragraph("Ingredients", styles['SubHeader']))
        
        # Add a note about total percentage
        percentage_status = "OK" if abs(total_percentage - 100) < 0.1 else "Warning"
        elements.append(Paragraph(f"Total Percentage: {total_percentage:.1f}% ({percentage_status})", styles['Normal']))
        elements.append(Spacer(1, 0.1*inch))
        
        # Create ingredients table for each phase
        for phase, ingredients in ingredients_by_phase.items():
            elements.append(Paragraph(f"Phase: {phase}", styles['Normal']))
            elements.append(Spacer(1, 0.05*inch))
            
            # Prepare data for the table
            ingredient_data = [["Ingredient", "INCI Name", "Percentage", "Function"]]
            for item in ingredients:
                # Wrap INCI names in paragraphs for better handling
                inci_paragraph = Paragraph(item["inci_name"], styles['INCI'])
                
                ingredient_data.append([
                    item["name"],
                    inci_paragraph,  # Use paragraph for INCI names
                    f"{item['percentage']}%",
                    item["function"] or "-"
                ])
            
            # Create the table with adjusted column widths based on content
            # Much wider INCI Name column in landscape mode
            ingredient_table = Table(
                ingredient_data, 
                colWidths=[2.5*inch, 4.5*inch, 1*inch, 2*inch],
                repeatRows=1  # Repeat header row if table spans multiple pages
            )
            
            # Add word wrapping for text content
            ingredient_table.setStyle(TableStyle([
                # Table borders and background
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                
                # Word wrapping for all cells
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                
                # Center the percentage column
                ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ]))
            
            elements.append(ingredient_table)
            elements.append(Spacer(1, 0.2*inch))
        
        # Manufacturing Steps
        if steps:
            elements.append(Paragraph("Manufacturing Steps", styles['SubHeader']))
            elements.append(Spacer(1, 0.1*inch))
            
            for i, step in enumerate(steps):
                elements.append(Paragraph(f"{i+1}. {step.description}", styles['Normal']))
                elements.append(Spacer(1, 0.1*inch))
        
        # Build the PDF document
        doc.build(elements)
        
        # Seek to the beginning of the buffer
        buffer.seek(0)
        
        # Return the PDF as a streaming response
        return StreamingResponse(
            buffer, 
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=formula_{formula.id}.pdf"}
        )
    
    elif format.lower() == "csv":
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(["Formula", formula.name])
        writer.writerow(["Type", formula.type])
        writer.writerow(["Total Weight", f"{formula.total_weight}g"])
        writer.writerow(["Created By", f"{user.first_name} {user.last_name}"])
        writer.writerow(["Created Date", formula.created_at.strftime("%Y-%m-%d")])
        if formula.description:
            writer.writerow(["Description", formula.description])
        
        writer.writerow([])  # Empty row as separator
        
        # Write ingredients header
        writer.writerow(["Phase", "Ingredient", "INCI Name", "Percentage", "Function"])
        
        # Write ingredients by phase
        for phase, ingredients in ingredients_by_phase.items():
            for item in ingredients:
                writer.writerow([
                    phase,
                    item["name"],
                    item["inci_name"],
                    item["percentage"],
                    item["function"] or "-"
                ])
        
        writer.writerow([])  # Empty row as separator
        
        # Write totals
        writer.writerow(["Total Percentage", f"{total_percentage:.1f}%"])
        
        writer.writerow([])  # Empty row as separator
        
        # Write manufacturing steps
        if steps:
            writer.writerow(["Manufacturing Steps"])
            for i, step in enumerate(steps):
                writer.writerow([f"{i+1}.", step.description])
        
        # Get the CSV data and return
        output.seek(0)
        return StreamingResponse(
            io.StringIO(output.getvalue()), 
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=formula_{formula.id}.csv"}
        )
    
    elif format.lower() == "json":
        # Create JSON
        data = {
            "formula": {
                "id": formula.id,
                "name": formula.name,
                "type": formula.type,
                "description": formula.description,
                "total_weight": formula.total_weight,
                "created_by": f"{user.first_name} {user.last_name}",
                "created_at": formula.created_at.isoformat(),
                "is_public": formula.is_public
            },
            "ingredients": {},
            "steps": [
                {
                    "order": step.order,
                    "description": step.description
                }
                for step in steps
            ],
            "total_percentage": round(total_percentage, 1)
        }
        
        # Add ingredients by phase
        for phase, ingredients in ingredients_by_phase.items():
            data["ingredients"][phase] = [
                {
                    "name": item["name"],
                    "inci_name": item["inci_name"],
                    "percentage": item["percentage"],
                    "function": item["function"]
                }
                for item in ingredients
            ]
        
        # Return JSON response
        return Response(
            content=json.dumps(data, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=formula_{formula.id}.json"}
        )
    
    elif format.lower() == "print":
        # Create a simplified HTML version
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Formula: {formula.name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 30px; }}
                h1 {{ color: #333; }}
                h2 {{ color: #555; margin-top: 20px; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .phase {{ font-weight: bold; margin-top: 15px; }}
                .steps {{ counter-reset: step; }}
                .step {{ margin-bottom: 8px; }}
                .step::before {{ 
                    counter-increment: step;
                    content: counter(step) ". ";
                    font-weight: bold;
                }}
                @media print {{
                    body {{ margin: 0; font-size: 12pt; }}
                    table {{ page-break-inside: avoid; }}
                }}
            </style>
        </head>
        <body>
            <h1>Formula: {formula.name}</h1>
            
            <h2>Basic Information</h2>
            <table>
                <tr><th>Type</th><td>{formula.type}</td></tr>
                <tr><th>Total Weight</th><td>{formula.total_weight}g</td></tr>
                <tr><th>Created By</th><td>{user.first_name} {user.last_name}</td></tr>
                <tr><th>Created Date</th><td>{formula.created_at.strftime("%Y-%m-%d")}</td></tr>
        """
        
        if formula.description:
            html_content += f"        <tr><th>Description</th><td>{formula.description}</td></tr>\n"
        
        html_content += """
            </table>
            
            <h2>Ingredients</h2>
        """
        
        # Add total percentage information
        percentage_status = "OK" if abs(total_percentage - 100) < 0.1 else "Warning"
        percentage_color = "#4CAF50" if abs(total_percentage - 100) < 0.1 else "#FF9800"
        html_content += f'<p>Total Percentage: <span style="color: {percentage_color};">{total_percentage:.1f}% ({percentage_status})</span></p>\n'
        
        # Add ingredients by phase
        for phase, ingredients in ingredients_by_phase.items():
            html_content += f'    <div class="phase">{phase}</div>\n'
            html_content += '    <table>\n'
            html_content += '        <tr><th>Ingredient</th><th>INCI Name</th><th>Percentage</th><th>Function</th></tr>\n'
            
            for item in ingredients:
                html_content += f'        <tr><td>{item["name"]}</td><td>{item["inci_name"]}</td><td>{item["percentage"]}%</td><td>{item["function"] or "-"}</td></tr>\n'
            
            html_content += '    </table>\n'
        
        # Add manufacturing steps
        if steps:
            html_content += '    <h2>Manufacturing Steps</h2>\n'
            html_content += '    <div class="steps">\n'
            
            for step in steps:
                html_content += f'        <div class="step">{step.description}</div>\n'
            
            html_content += '    </div>\n'
        
        html_content += """
        </body>
        </html>
        """
        
        return Response(
            content=html_content,
            media_type="text/html",
            headers={"Content-Disposition": f"inline; filename=formula_{formula.id}.html"}
        )
    
    else:
        raise HTTPException(status_code=400, detail="Invalid export format. Supported formats: pdf, csv, json, print")