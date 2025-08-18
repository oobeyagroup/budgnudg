# devtools/middleware.py
import logging
import re
import threading
from django.conf import settings
from django.template.response import TemplateResponse
from django.template import Template
from django.template.backends.django import Template as DjangoTemplate

logger = logging.getLogger(__name__)

# Thread-local storage to track templates used during request processing
_thread_local = threading.local()

class TemplateLoggingMiddleware:
    """
    Development-only middleware that logs the template(s) used to render a response.
    Works only when DEBUG=True.
    
    Handles both:
    - TemplateResponse objects (from CBVs using TemplateView, ListView, etc.)
    - HttpResponse objects (from FBVs using render() or CBVs using basic View)
    """
    def __init__(self, get_response):
        self.get_response = get_response
        if settings.DEBUG:
            self._patch_template_render()
            logger.info("Template logging middleware initialized with template render patching")

    def __call__(self, request):
        # Initialize thread-local storage for this request
        _thread_local.templates_used = []
        _thread_local.request_path = getattr(request, 'path', 'unknown')
        
        response = self.get_response(request)
        
        # Only log templates when DEBUG is True
        if settings.DEBUG:
            self._log_template_from_response(request, response)
        
        # Clean up thread-local storage
        if hasattr(_thread_local, 'templates_used'):
            delattr(_thread_local, 'templates_used')
        if hasattr(_thread_local, 'request_path'):
            delattr(_thread_local, 'request_path')
        
        return response

    def _patch_template_render(self):
        """
        Patch Django's template rendering to track which templates are used.
        This works for both CBVs and FBVs.
        """
        # Store original render method
        original_render = Template.render
        
        def patched_render(self, context):
            # Track this template usage
            if hasattr(_thread_local, 'templates_used'):
                template_name = getattr(self, 'name', None)
                if template_name and template_name not in _thread_local.templates_used:
                    _thread_local.templates_used.append(template_name)
            
            # Call original render method
            return original_render(self, context)
        
        # Apply the patch
        Template.render = patched_render

    def _log_template_from_response(self, request, response):
        """Log template information from the response."""
        template_names = []
        
        # Method 1: Check if this is a TemplateResponse (CBVs with proper generic views)
        if isinstance(response, TemplateResponse):
            template_name = getattr(response, 'template_name', None)
            if template_name:
                if isinstance(template_name, list):
                    template_names.extend(template_name)
                else:
                    template_names.append(str(template_name))
        
        # Method 2: Check thread-local storage for templates used during rendering
        if hasattr(_thread_local, 'templates_used') and _thread_local.templates_used:
            for template_name in _thread_local.templates_used:
                if template_name not in template_names:
                    template_names.append(template_name)
        
        # Method 3: Check response context data (some CBVs)
        if hasattr(response, 'context_data') and response.context_data:
            context_template = response.context_data.get('template_name')
            if context_template and context_template not in template_names:
                template_names.append(context_template)
        
        # Method 4: Fallback - extract from HTML content
        if not template_names and hasattr(response, 'content'):
            template_names.extend(self._extract_templates_from_content(response.content))
        
        # Log the templates if any were found
        if template_names:
            template_str = ', '.join(template_names)
            message = f"[TEMPLATE] {request.path} -> {template_str}"
            logger.debug(message)
            print(message)  # Also print to console for immediate visibility
        
        # Debug: Only show this if no templates were detected (for troubleshooting)
        elif request.path not in ['/favicon.ico', '/apple-touch-icon.png', '/apple-touch-icon-precomposed.png']:
            print(f"DEBUG: No template detected for {request.path} (Response type: {type(response).__name__})")

    def _extract_templates_from_content(self, content):
        """
        Extract template names from Django's debug template comments in HTML content.
        Django automatically adds these comments when DEBUG=True.
        """
        template_names = []
        
        try:
            # Decode content if it's bytes
            if isinstance(content, bytes):
                html_content = content.decode('utf-8', errors='ignore')
            else:
                html_content = str(content)
            
            # Look for Django template debug comments
            # Pattern: <!-- Template: path/to/template.html -->
            template_pattern = r'<!-- Template: ([^>]+) -->'
            matches = re.findall(template_pattern, html_content)
            
            # Clean up the matches and add to list
            for match in matches:
                template_name = match.strip()
                if template_name and template_name not in template_names:
                    template_names.append(template_name)
            
            # Fallback: Look for common Django template patterns in HTML
            if not template_names:
                template_names.extend(self._guess_templates_from_html(html_content))
                
        except Exception as e:
            logger.debug(f"Error extracting templates from content: {e}")
        
        return template_names

    def _guess_templates_from_html(self, html_content):
        """
        Fallback method to guess templates from HTML structure.
        This is less reliable but can help identify templates when debug comments aren't available.
        """
        template_names = []
        
        try:
            # Look for common template file patterns in title or meta tags
            title_match = re.search(r'<title[^>]*>([^<]*)</title>', html_content, re.IGNORECASE)
            if title_match:
                title_content = title_match.group(1).strip()
                # This is a heuristic - not always accurate
                if 'Import' in title_content:
                    template_names.append('import_form.html (guessed from title)')
                elif 'Transaction' in title_content:
                    template_names.append('transaction_template.html (guessed from title)')
                    
        except Exception as e:
            logger.debug(f"Error guessing templates from HTML: {e}")
        
        return template_names
