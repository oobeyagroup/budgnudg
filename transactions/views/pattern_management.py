from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Sum, Count, Q, Max
from ..models import LearnedSubcat, LearnedPayoree, Transaction
from ..categorization import extract_merchant_from_description
import json

def pattern_management(request):
    """Main pattern management interface"""
    # Get patterns with statistics
    subcat_patterns = (LearnedSubcat.objects
                      .values('key')
                      .annotate(
                          total_count=Sum('count'),
                          category_count=Count('subcategory', distinct=True),
                          last_activity=Max('last_seen')
                      )
                      .order_by('-total_count'))
    
    payoree_patterns = (LearnedPayoree.objects
                       .values('key') 
                       .annotate(
                           total_count=Sum('count'),
                           payoree_count=Count('payoree', distinct=True),
                           last_activity=Max('last_seen')
                       )
                       .order_by('-total_count'))
    
    context = {
        'subcat_patterns': subcat_patterns[:50],  # Limit to top 50
        'payoree_patterns': payoree_patterns[:50],
        'total_subcat_patterns': subcat_patterns.count(),
        'total_payoree_patterns': payoree_patterns.count()
    }
    
    return render(request, 'transactions/pattern_management.html', context)

def pattern_detail(request, pattern_key):
    """Show details for a specific pattern"""
    # Get all learned records for this key
    subcats = LearnedSubcat.objects.filter(key=pattern_key).select_related('subcategory__parent')
    payorees = LearnedPayoree.objects.filter(key=pattern_key).select_related('payoree')
    
    # Find sample transactions that match this pattern
    sample_transactions = Transaction.objects.filter(
        description__icontains=pattern_key
    ).order_by('-date')[:10]
    
    # Test current extraction
    current_extraction = None
    if sample_transactions.exists():
        sample_desc = sample_transactions.first().description
        current_extraction = extract_merchant_from_description(sample_desc)
    
    context = {
        'pattern_key': pattern_key,
        'subcats': subcats,
        'payorees': payorees,
        'sample_transactions': sample_transactions,
        'current_extraction': current_extraction,
        'extraction_matches': current_extraction == pattern_key
    }
    
    return render(request, 'transactions/pattern_detail.html', context)

@require_POST
def merge_patterns(request):
    """AJAX endpoint to merge patterns"""
    try:
        data = json.loads(request.body)
        old_key = data['old_key'].upper()
        new_key = data['new_key'].upper()
        
        if old_key == new_key:
            return JsonResponse({'success': False, 'error': 'Cannot merge pattern with itself'})
        
        merged_count = 0
        
        # Merge subcategory patterns
        old_subcats = LearnedSubcat.objects.filter(key=old_key)
        for old_subcat in old_subcats:
            new_subcat, created = LearnedSubcat.objects.get_or_create(
                key=new_key,
                subcategory=old_subcat.subcategory,
                defaults={'count': 0, 'last_seen': old_subcat.last_seen}
            )
            new_subcat.count += old_subcat.count
            new_subcat.save()
            old_subcat.delete()
            merged_count += 1
        
        # Merge payoree patterns  
        old_payorees = LearnedPayoree.objects.filter(key=old_key)
        for old_payoree in old_payorees:
            new_payoree, created = LearnedPayoree.objects.get_or_create(
                key=new_key,
                payoree=old_payoree.payoree,
                defaults={'count': 0, 'last_seen': old_payoree.last_seen}
            )
            new_payoree.count += old_payoree.count
            new_payoree.save()
            old_payoree.delete()
            merged_count += 1
        
        return JsonResponse({
            'success': True, 
            'message': f'Merged {merged_count} patterns from "{old_key}" into "{new_key}"'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@require_POST 
def rename_pattern(request):
    """AJAX endpoint to rename a pattern"""
    try:
        data = json.loads(request.body)
        old_key = data['old_key'].upper()
        new_key = data['new_key'].upper()
        
        if old_key == new_key:
            return JsonResponse({'success': False, 'error': 'Old and new keys are the same'})
        
        # Check if new key already exists
        if (LearnedSubcat.objects.filter(key=new_key).exists() or 
            LearnedPayoree.objects.filter(key=new_key).exists()):
            return JsonResponse({
                'success': False, 
                'error': f'Pattern "{new_key}" already exists. Use merge instead.'
            })
        
        # Rename patterns
        subcat_count = LearnedSubcat.objects.filter(key=old_key).update(key=new_key)
        payoree_count = LearnedPayoree.objects.filter(key=old_key).update(key=new_key)
        
        total_updated = subcat_count + payoree_count
        
        return JsonResponse({
            'success': True,
            'message': f'Renamed {total_updated} patterns from "{old_key}" to "{new_key}"'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def test_extraction(request):
    """AJAX endpoint to test merchant extraction"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            description = data['description']
            
            extracted = extract_merchant_from_description(description)
            
            # Check for existing patterns
            subcat_matches = list(LearnedSubcat.objects.filter(key=extracted).values(
                'subcategory__name', 'subcategory__parent__name', 'count'
            ))
            payoree_matches = list(LearnedPayoree.objects.filter(key=extracted).values(
                'payoree__name', 'count'
            ))
            
            return JsonResponse({
                'success': True,
                'extracted': extracted,
                'subcat_matches': subcat_matches,
                'payoree_matches': payoree_matches
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'POST method required'})

def search_patterns(request):
    """AJAX endpoint to search patterns"""
    query = request.GET.get('q', '').upper()
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    # Search both subcategory and payoree patterns
    subcat_results = list(LearnedSubcat.objects.filter(
        key__icontains=query
    ).values('key').distinct())
    
    payoree_results = list(LearnedPayoree.objects.filter(
        key__icontains=query  
    ).values('key').distinct())
    
    # Combine and deduplicate
    all_keys = set()
    for result in subcat_results + payoree_results:
        all_keys.add(result['key'])
    
    results = [{'key': key} for key in sorted(all_keys)]
    
    return JsonResponse({'results': results[:20]})  # Limit to 20 results
