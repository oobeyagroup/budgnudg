"""
Budget Wizard Service

Orchestrates the budget creation wizard flow, integrating baseline calculations
with AI suggestions and user preferences.
"""
from typing import Dict, List, Any, Optional
from decimal import Decimal
from datetime import date, timedelta
from calendar import monthrange

from django.db import transaction
from django.utils import timezone

from .baseline_calculator import BaselineCalculator
from ..models import Budget, BudgetPeriod
from transactions.utils import trace


def add_months(source_date: date, months: int) -> date:
    """Add months to a date, handling month/year overflow."""
    month = source_date.month - 1 + months
    year = source_date.year + month // 12
    month = month % 12 + 1
    day = min(source_date.day, monthrange(year, month)[1])
    return date(year, month, day)


class BudgetWizard:
    """Orchestrates the budget creation wizard flow."""
    
    def __init__(self, baseline_calculator: Optional[BaselineCalculator] = None):
        self.baseline_calculator = baseline_calculator or BaselineCalculator()
    
    @trace
    def generate_budget_draft(
        self, 
        target_months: int = 3,
        method: str = 'median',
        starting_year: Optional[int] = None,
        starting_month: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate initial budget draft based on historical data.
        
        Returns dict with:
        - budget_items: List of suggested budget entries
        - summary: Aggregate statistics
        - period_info: Details about target periods
        """
        # Determine starting period
        if not starting_year or not starting_month:
            today = date.today()
            # Start with next month by default
            next_month = add_months(today, 1)
            starting_year = next_month.year
            starting_month = next_month.month
        
        # Get baseline suggestions
        suggestions = self.baseline_calculator.get_category_suggestions(
            target_months=target_months,
            method=method
        )
        
        # Generate target periods
        periods = []
        current_date = date(starting_year, starting_month, 1)
        for i in range(target_months):
            period_date = add_months(current_date, i)
            periods.append({
                'year': period_date.year,
                'month': period_date.month,
                'display': period_date.strftime('%B %Y')
            })
        
        # Calculate summary statistics
        total_baseline = sum(item['baseline_amount'] for item in suggestions)
        total_suggested = sum(item['suggested_amount'] for item in suggestions)
        total_variance = total_suggested - total_baseline
        
        return {
            'budget_items': suggestions,
            'periods': periods,
            'summary': {
                'total_baseline': total_baseline,
                'total_suggested': total_suggested,
                'total_variance': total_variance,
                'variance_percentage': float((total_variance / total_baseline * 100)) if total_baseline else 0,
                'item_count': len(suggestions)
            },
            'method_used': method
        }
from typing import Dict, List, Any, Optional
from decimal import Decimal
from datetime import date, timedelta
from calendar import monthrange

from django.db import transaction
from django.utils import timezone

from .baseline_calculator import BaselineCalculator
from ..models import Budget, BudgetPeriod
from transactions.utils import trace


class BudgetWizard:
    """Orchestrates the budget creation wizard flow."""
    
    def __init__(self, baseline_calculator: Optional[BaselineCalculator] = None):
        self.baseline_calculator = baseline_calculator or BaselineCalculator()
    
    @trace
    def generate_budget_draft(
        self, 
        target_months: int = 3,
        method: str = 'median',
        starting_year: Optional[int] = None,
        starting_month: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate initial budget draft based on historical data.
        
        Returns dict with:
        - budget_items: List of suggested budget entries
        - summary: Aggregate statistics
        - period_info: Details about target periods
        """
        # Determine starting period
        if not starting_year or not starting_month:
            today = date.today()
            # Start with next month by default
            next_month = add_months(today, 1)
            starting_year = next_month.year
            starting_month = next_month.month
        
        # Get baseline suggestions
        suggestions = self.baseline_calculator.get_category_suggestions(
            target_months=target_months,
            method=method
        )
        
        # Generate target periods
        periods = []
        current_date = date(starting_year, starting_month, 1)
        for i in range(target_months):
            period_date = add_months(current_date, i)
            periods.append({
                'year': period_date.year,
                'month': period_date.month,
                'display': period_date.strftime('%B %Y')
            })
        
        # Calculate summary statistics
        total_baseline = sum(item['baseline_amount'] for item in suggestions)
        total_suggested = sum(item['suggested_amount'] for item in suggestions)
        total_variance = total_suggested - total_baseline
        
        return {
            'budget_items': suggestions,
            'periods': periods,
            'summary': {
                'total_baseline': total_baseline,
                'total_suggested': total_suggested,
                'total_variance': total_variance,
                'variance_percentage': float((total_variance / total_baseline * 100)) if total_baseline else 0,
                'item_count': len(suggestions)
            },
            'method_used': method
        }
    
    @trace
    def apply_ai_suggestions(
        self, 
        draft_items: List[Dict],
        adjustment_preferences: Optional[Dict[str, float]] = None
    ) -> List[Dict]:
        """
        Apply AI suggestions to budget draft items.
        
        Leverages existing categorization AI and applies smart adjustments
        based on needs levels and spending patterns.
        """
        if not adjustment_preferences:
            adjustment_preferences = {
                'critical': 1.05,      # 5% buffer for critical needs
                'core': 1.02,          # 2% buffer for core needs  
                'lifestyle': 0.95,     # 5% reduction for lifestyle
                'discretionary': 0.90, # 10% reduction for discretionary
                'luxury': 0.85,        # 15% reduction for luxury
                'deferred': 0.80       # 20% reduction for deferred
            }
        
        enhanced_items = []
        
        for item in draft_items:
            # Apply needs-level based adjustment
            needs_level = item.get('needs_level')
            adjustment_factor = adjustment_preferences.get(needs_level, 1.0)
            
            # Calculate AI-enhanced suggestion
            baseline = item['baseline_amount']
            ai_suggested = baseline * Decimal(str(adjustment_factor))
            
            # Round to nearest dollar for cleaner budgets
            ai_suggested = ai_suggested.quantize(Decimal('1'))
            
            # Add confidence score based on supporting data
            support = item.get('support', {})
            n_months = support.get('n_months', 0)
            n_transactions = support.get('total_transactions', 0)
            
            # Simple confidence scoring
            confidence = min(0.95, max(0.5, (n_months / 12.0) * (min(n_transactions, 50) / 50.0)))
            
            enhanced_item = item.copy()
            enhanced_item.update({
                'ai_suggested_amount': ai_suggested,
                'adjustment_factor': adjustment_factor,
                'confidence': confidence,
                'ai_reasoning': self._generate_ai_reasoning(item, adjustment_factor)
            })
            
            enhanced_items.append(enhanced_item)
        
        return enhanced_items
    
    def _generate_ai_reasoning(self, item: Dict, adjustment_factor: float) -> str:
        """Generate human-readable reasoning for AI suggestions."""
        needs_level = item.get('needs_level', 'unknown')
        support = item.get('support', {})
        n_months = support.get('n_months', 0)
        variance_pct = item.get('variance_pct', 0)
        
        reasoning_parts = []
        
        # Base data confidence
        if n_months >= 6:
            reasoning_parts.append(f"Based on {n_months} months of data")
        else:
            reasoning_parts.append(f"Limited data ({n_months} months)")
        
        # Adjustment reasoning
        if adjustment_factor > 1.0:
            pct = (adjustment_factor - 1.0) * 100
            reasoning_parts.append(f"+{pct:.0f}% buffer for {needs_level} needs")
        elif adjustment_factor < 1.0:
            pct = (1.0 - adjustment_factor) * 100
            reasoning_parts.append(f"-{pct:.0f}% reduction target for {needs_level} spending")
        else:
            reasoning_parts.append("Baseline amount maintained")
        
        return ". ".join(reasoning_parts) + "."
    
    @trace
    def commit_budget_draft(
        self,
        budget_items: List[Dict],
        target_periods: List[Dict],
        overwrite_existing: bool = True
    ) -> Dict[str, Any]:
        """
        Commit budget items to database for specified periods.
        
        Creates Budget and BudgetPeriod records, with optional overwrite of existing.
        """
        created_budgets = []
        updated_budgets = []
        created_periods = []
        
        with transaction.atomic():
            for period in target_periods:
                year, month = period['year'], period['month']
                
                # Create or get budget period
                budget_period, period_created = BudgetPeriod.objects.get_or_create(
                    year=year,
                    month=month,
                    defaults={'notes': f'Created via Budget Wizard'}
                )
                
                if period_created:
                    created_periods.append(budget_period)
                
                # Process budget items for this period
                for item in budget_items:
                    budget_data = {
                        'year': year,
                        'month': month,
                        'category_id': item.get('category_id'),
                        'subcategory_id': item.get('subcategory_id'),
                        'payoree_id': item.get('payoree_id'),
                        'needs_level': item.get('needs_level'),
                        'amount': item.get('suggested_amount') or item.get('ai_suggested_amount'),
                        'baseline_amount': item.get('baseline_amount'),
                        'is_ai_suggested': True,
                        'user_note': f"Generated by Budget Wizard using {item.get('method_used', 'median')} method"
                    }
                    
                    # Remove None values to avoid unique constraint issues
                    budget_data = {k: v for k, v in budget_data.items() if v is not None}
                    
                    if overwrite_existing:
                        # Update or create
                        budget, budget_created = Budget.objects.update_or_create(
                            year=year,
                            month=month,
                            category_id=budget_data.get('category_id'),
                            subcategory_id=budget_data.get('subcategory_id'),
                            payoree_id=budget_data.get('payoree_id'),
                            needs_level=budget_data.get('needs_level'),
                            defaults=budget_data
                        )
                        
                        if budget_created:
                            created_budgets.append(budget)
                        else:
                            updated_budgets.append(budget)
                    else:
                        # Only create if doesn't exist
                        try:
                            budget = Budget.objects.create(**budget_data)
                            created_budgets.append(budget)
                        except Exception:
                            # Budget already exists, skip
                            pass
                
                # Update period totals
                budget_period.update_totals()
        
        return {
            'created_budgets': len(created_budgets),
            'updated_budgets': len(updated_budgets),
            'created_periods': len(created_periods),
            'periods_processed': len(target_periods),
            'success': True
        }
    
    @trace
    def get_existing_budget_summary(
        self, 
        year: int, 
        month: int
    ) -> Optional[Dict[str, Any]]:
        """Get summary of existing budgets for a given period."""
        try:
            period = BudgetPeriod.objects.get(year=year, month=month)
            budgets = Budget.objects.filter(year=year, month=month).select_related(
                'category', 'subcategory', 'payoree'
            )
            
            return {
                'period': period,
                'budget_count': len(budgets),
                'total_budgeted': period.total_budgeted,
                'baseline_total': period.baseline_total,
                'is_finalized': period.is_finalized,
                'budgets': list(budgets)
            }
        except BudgetPeriod.DoesNotExist:
            return None