#!/usr/bin/env python
import os
import django
from django.conf import settings

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'budgnudg.settings')
django.setup()

from transactions.models import KeywordRule, Category
from transactions.views.category_training import CategoryTrainingSessionView
from django.test import RequestFactory
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.auth.models import User

def test_keyword_rule_creation_direct():
    print("=== Testing Keyword Rule Creation Direct View Method ===")
    
    # Count existing rules
    initial_count = KeywordRule.objects.count()
    print(f"Initial keyword rules: {initial_count}")
    
    # Get an existing category (Uncategorized)
    category = Category.objects.filter(name="Uncategorized").first()
    if not category:
        category = Category.objects.first()
    print(f"Using category: {category.name} (ID: {category.id})")
    
    # Create request factory and request
    factory = RequestFactory()
    request = factory.post('/transactions/training/session/', {
        'category': str(category.id),
        'subcategory': '',
        'action': 'save_and_next',
        'create_keyword_rule': 'on',  # Checkbox checked
        'keyword_rule_text': 'DIRECT_TEST_KEYWORD',
        'keyword_rule_priority': '600',
        'train_merchant_pattern': '',
        'train_description_pattern': 'on'
    })
    
    # Set up session with training patterns
    session = SessionStore()
    patterns = [{
        'pattern_key': 'DIRECT_TEST_PATTERN',
        'representative_description': 'DIRECT TEST PURCHASE',
        'extracted_merchant': 'TEST_MERCHANT',
        'potential_keywords': ['TEST', 'DIRECT']
    }]
    session['training_patterns'] = patterns
    session['current_pattern_index'] = 0
    session.save()
    request.session = session
    
    # Set up messages framework
    setattr(request, '_messages', FallbackStorage(request))
    
    # Create user
    user = User.objects.first()
    if not user:
        user = User.objects.create_user('testuser', 'test@example.com', 'password')
    request.user = user
    
    print(f"POST data: {dict(request.POST)}")
    print(f"Session patterns: {request.session.get('training_patterns')}")
    
    # Create view and call POST method directly
    view = CategoryTrainingSessionView()
    view.setup(request)
    
    try:
        response = view.post(request)
        print(f"Response status: {response.status_code}")
        
        # Check if keyword rule was created
        final_count = KeywordRule.objects.count()
        print(f"Final keyword rules: {final_count}")
        
        if final_count > initial_count:
            new_rule = KeywordRule.objects.filter(keyword='DIRECT_TEST_KEYWORD').first()
            if new_rule:
                print(f"✅ SUCCESS: Created rule: {new_rule.keyword} -> {new_rule.category.name} (priority: {new_rule.priority})")
            else:
                print("❌ New rule count increased but can't find DIRECT_TEST_KEYWORD rule")
                print("New rules:")
                for rule in KeywordRule.objects.order_by('-id')[:3]:
                    print(f"  {rule.keyword} -> {rule.category.name} (priority: {rule.priority})")
        else:
            print("❌ FAILED: No new keyword rule created")
            
        # Show what happened in the POST method
        print("\n=== Debugging POST method logic ===")
        print(f"create_keyword_rule: {request.POST.get('create_keyword_rule')}")
        print(f"keyword_rule_text: {request.POST.get('keyword_rule_text')}")
        print(f"keyword_rule_priority: {request.POST.get('keyword_rule_priority')}")
        print(f"selected_category: {category}")
        print(f"category.id: {category.id}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_keyword_rule_creation_direct()
