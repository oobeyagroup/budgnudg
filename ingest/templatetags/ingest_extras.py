from django import template
import json

register = template.Library()

@register.filter
def get_item(d, key):
    try:
        return d.get(key, "")
    except AttributeError:
        return ""

@register.filter
def jsonify(obj):
    """Convert a Python object into JSON string for template use"""
    return json.dumps(obj)

@register.simple_tag
def is_selected(value1, value2):
    """Compare two values and return 'selected' if they match"""
    return 'selected' if str(value1) == str(value2) else ''
    