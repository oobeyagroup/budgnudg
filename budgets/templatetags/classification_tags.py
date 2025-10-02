"""
Template tags for Budget by Classification Analysis feature.

Provides filters and tags for accessing dictionary data and formatting
budget/historical values in the classification analysis template.
"""

from django import template
from decimal import Decimal
import decimal

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Template filter to get item from dictionary by key.

    Usage: {{ mydict|get_item:mykey }}

    Args:
        dictionary: Dictionary to access
        key: Key to look up

    Returns:
        Value from dictionary or None if key doesn't exist
    """
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def format_currency(value):
    """
    Format a value as currency.

    Usage: {{ amount|format_currency }}

    Args:
        value: Numeric value to format

    Returns:
        Formatted currency string (e.g., "$123.45")
    """
    if value is None or value == "":
        return "$0.00"

    try:
        # Convert to Decimal for precise formatting
        if isinstance(value, str):
            value = Decimal(value)
        elif not isinstance(value, Decimal):
            value = Decimal(str(value))

        # Format with 2 decimal places
        return f"${value:.2f}"
    except (ValueError, TypeError, decimal.InvalidOperation):
        return "$0.00"


@register.simple_tag
def month_key(year, month):
    """
    Generate a month key for dictionary lookup.

    Usage: {% month_key year month as key %}{{ data|get_item:key }}

    Args:
        year: Year (int)
        month: Month (int)

    Returns:
        String in format "YYYY-MM" (e.g., "2025-10")
    """
    try:
        return f"{int(year)}-{int(month):02d}"
    except (ValueError, TypeError):
        return "0000-00"


@register.filter
def multiply(value, arg):
    """
    Multiply two values.

    Usage: {{ value|multiply:multiplier }}

    Args:
        value: First value
        arg: Second value (multiplier)

    Returns:
        Product of the two values
    """
    try:
        return Decimal(str(value)) * Decimal(str(arg))
    except (ValueError, TypeError, decimal.InvalidOperation):
        return 0


@register.filter
def subtract(value, arg):
    """
    Subtract second value from first.

    Usage: {{ value|subtract:amount }}

    Args:
        value: First value (minuend)
        arg: Second value (subtrahend)

    Returns:
        Difference between the values
    """
    try:
        return Decimal(str(value)) - Decimal(str(arg))
    except (ValueError, TypeError, decimal.InvalidOperation):
        return 0


@register.filter
def abs_value(value):
    """
    Get absolute value.

    Usage: {{ value|abs_value }}

    Args:
        value: Numeric value

    Returns:
        Absolute value
    """
    try:
        return abs(Decimal(str(value)))
    except (ValueError, TypeError, decimal.InvalidOperation):
        return 0


@register.simple_tag(takes_context=True)
def allocation_id_for_month(context, year, month):
    """
    Get allocation ID for a specific month.

    Usage: {% allocation_id_for_month year month %}

    Args:
        context: Template context
        year: Year (int)
        month: Month (int)

    Returns:
        Allocation ID for the given month, or empty string if none exists
    """
    try:
        month_key = f"{int(year)}-{int(month):02d}"
        allocation_by_month = context.get("allocation_by_month", {})

        if month_key in allocation_by_month:
            return allocation_by_month[month_key].id
        return ""
    except (ValueError, TypeError, AttributeError):
        return ""
