from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def mult(value, arg):
    """Multiply value by arg"""
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def index(sequence, position):
    """Get item at position in sequence"""
    try:
        return sequence[int(position)]
    except (IndexError, TypeError, ValueError):
        return None
