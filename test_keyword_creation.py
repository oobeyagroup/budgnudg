#!/usr/bin/env python
import os
import django
from django.conf import settings

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'budgnudg.settings')
django.setup()

from transactions.models import KeywordRule, Category
from django.test import RequestFactory, Client
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.auth.models import User
from django.urls import reverse

def test_keyword_rule_creation():
    print("=== Testing Keyword Rule Creation Through Training Session ===")
    
    # Count existing rules
    initial_count = KeywordRule.objects.count()
    print(f"Initial keyword rules: {initial_count}")
    
    # Get or create category
    category, created = Category.objects.get_or_create(
        name="Test Category",
        defaults={'type': 'expense'}
    )
    print(f"Using category: {category.name} (ID: {category.id})")
    
    # Create test client and user
    client = Client()
    user, created = User.objects.get_or_create(
        username='testuser',
        defaults={'email': 'test@example.com'}
    )
    client.force_login(user)
    
    # Set up session with training patterns
    session = client.session
    patterns = [{
        'pattern_key': 'TEST_PATTERN',
        'representative_description': 'TEST STARBUCKS COFFEE',
        'extracted_merchant': 'STARBUCKS',
        'potential_keywords': ['STARBUCKS', 'COFFEE']
    }]
    session['training_patterns'] = patterns
    session['current_pattern_index'] = 0
    session.save()
    
    # Test POST data
    post_data = {
        'category': str(category.id),
        'subcategory': '',
        'action': 'save_and_next',
        'create_keyword_rule': 'on',  # Checkbox checked
        'keyword_rule_text': 'TEST_COFFEE_SHOP',
        'keyword_rule_priority': '500',
        'train_merchant_pattern': '',
        'train_description_pattern': 'on'
    }
    
    print(f"POST data: {post_data}")
    
    # Make the request
    url = reverse('transactions:category_training_session')
    response = client.post(url, post_data)
    
    print(f"Response status: {response.status_code}")
    
    # Check if keyword rule was created
    final_count = KeywordRule.objects.count()
    print(f"Final keyword rules: {final_count}")
    
    if final_count > initial_count:
        new_rule = KeywordRule.objects.filter(keyword='TEST_COFFEE_SHOP').first()
        if new_rule:
            print(f"✅ SUCCESS: Created rule: {new_rule.keyword} -> {new_rule.category.name} (priority: {new_rule.priority})")
        else:
            print("❌ New rule count increased but can't find TEST_COFFEE_SHOP rule")
    else:
        print("❌ FAILED: No new keyword rule created")
        
    # Show recent rules
    recent_rules = KeywordRule.objects.order_by('-id')[:3]
    print("Recent keyword rules:")
    for rule in recent_rules:
        print(f"  {rule.keyword} -> {rule.category.name} (priority: {rule.priority})")

if __name__ == "__main__":
    test_keyword_rule_creation()
