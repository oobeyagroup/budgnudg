# devtools/middleware.py
import logging
from django.conf import settings
from django.template.response import TemplateResponse

logger = logging.getLogger(__name__)

class TemplateLoggingMiddleware:
    """
    Development-only middleware that logs the template(s) used to render a response.
    Works only when DEBUG=True.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        if settings.DEBUG:
            logger.info("Template logging middleware initialized")

    def __call__(self, request):
        response = self.get_response(request)
        
        # Only log templates when DEBUG is True
        if settings.DEBUG:
            self._log_template_from_response(request, response)
        
        return response

    def _log_template_from_response(self, request, response):
        """Log template information from the response."""
        
        # Check if this is a TemplateResponse and log the template name
        if isinstance(response, TemplateResponse):
            template_name = getattr(response, 'template_name', None)
            if template_name:
                # Handle both single template names and lists of template names
                if isinstance(template_name, list):
                    template_str = ', '.join(template_name)
                else:
                    template_str = str(template_name)
                
                message = f"[TEMPLATE] {request.path} -> {template_str}"
                logger.debug(message)
                print(message)  # Also print to console for immediate visibility
