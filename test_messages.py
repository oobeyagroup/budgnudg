#!/usr/bin/env python
"""
Simple test script to trigger Django messages and test auto-fade functionality
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'budgnudg.settings')
django.setup()

from django.http import HttpRequest, HttpResponse
from django.contrib.messages import success, info, warning, error
from django.shortcuts import render
from django.template.response import TemplateResponse
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware

def test_messages_view(request):
    """Test view to generate different types of messages"""
    
    # Add different types of messages
    success(request, "This is a success message that should fade after 5 seconds!")
    info(request, "This is an info message that should also fade automatically.")
    warning(request, "This is a warning message - watch it disappear!")
    error(request, "This is an error message that will auto-fade too.")
    
    # Simple template content
    template_content = """
    {% load static %}
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Messages Auto-Fade</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body>
        <div class="container mt-4">
            <h1>Test Messages Auto-Fade</h1>
            <p>The messages above should automatically fade and disappear after 5 seconds.</p>
            
            {% include "partials/_messages.html" %}
            
            <div class="mt-4">
                <p>Watch the messages above - they should fade out automatically after 5 seconds!</p>
                <a href="{% url 'home' %}" class="btn btn-primary">Back to Home</a>
            </div>
        </div>
        
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """
    
    return HttpResponse(template_content)

if __name__ == "__main__":
    print("Test script created. Add this to your URLs to test the auto-fade functionality:")
    print("path('test-messages/', test_messages_view, name='test_messages'),")
