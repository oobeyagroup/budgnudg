from django import template

register = template.Library()


@register.filter
def lookup(dictionary, key):
    """Template filter to look up a dictionary value by key"""
    if dictionary and hasattr(dictionary, "get"):
        return dictionary.get(key, 0)  # Return 0 instead of {} for missing keys
    return 0


@register.filter
def get_item(dictionary, key):
    """Alternative template filter to get dictionary item"""
    return dictionary.get(key) if dictionary else None
