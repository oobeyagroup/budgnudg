# transactions/views/category_training.py
from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.db import transaction as db_transaction
from django.utils import timezone
from transactions.models import Transaction, Category, Payoree, LearnedSubcat, LearnedPayoree
from transactions.forms import TransactionImportForm
from transactions.utils import trace, read_uploaded_file
from transactions.services.mapping import map_file_for_profile
from transactions.categorization import categorize_transaction, suggest_subcategory, categorize_transaction_with_reasoning
import logging
import json
from collections import defaultdict
import csv
from io import StringIO

logger = logging.getLogger(__name__)


class CategoryTrainingUploadView(View):
    """Upload CSV files for category training purposes."""
    template_name = "transactions/category_training_upload.html"

    @method_decorator(trace)
    def get(self, request):
        from ingest.models import MappingProfile
        
        # Get available mapping profiles
        profiles = MappingProfile.objects.all()
        profile_choices = [(p.id, p.name) for p in profiles]
        
        form = TransactionImportForm(
            profile_choices=profile_choices,
            account_choices=[('training', 'Training Data')]  # Dummy account for training
        )
        
        return render(request, self.template_name, {
            'form': form,
            'title': 'Category Training - Upload CSV'
        })

    @method_decorator(trace)
    def post(self, request):
        from ingest.models import MappingProfile
        
        logger.info("CategoryTrainingUploadView POST request received")
        
        profiles = MappingProfile.objects.all()
        profile_choices = [(p.id, p.name) for p in profiles]
        
        form = TransactionImportForm(
            request.POST,
            request.FILES,
            profile_choices=profile_choices,
            account_choices=[('training', 'Training Data')]
        )
        
        logger.info(f"Form is_valid: {form.is_valid()}")
        if not form.is_valid():
            logger.error(f"Form errors: {form.errors}")
        
        if form.is_valid():
            file = request.FILES['file']
            profile_id = form.cleaned_data['mapping_profile']
            
            try:
                profile = MappingProfile.objects.get(id=profile_id)
            except MappingProfile.DoesNotExist:
                messages.error(request, "Invalid mapping profile selected.")
                return render(request, self.template_name, {'form': form})
            
            # Store in session for training analysis
            request.session['training_file'] = read_uploaded_file(file)
            request.session['training_profile_id'] = profile_id
            request.session['training_filename'] = file.name
            
            return redirect('category_training_analyze')
        
        return render(request, self.template_name, {
            'form': form,
            'title': 'Category Training - Upload CSV'
        })


class CategoryTrainingAnalyzeView(View):
    """Analyze uploaded CSV and extract unique transaction patterns for training."""
    template_name = "transactions/category_training_analyze.html"

    @method_decorator(trace)
    def get(self, request):
        # Retrieve upload data from session
        try:
            file_content = request.session['training_file']
            profile_id = request.session['training_profile_id']
            filename = request.session['training_filename']
        except KeyError:
            messages.error(request, "No training file found. Please upload a CSV first.")
            return redirect('category_training_upload')
        
        from ingest.models import MappingProfile
        try:
            profile = MappingProfile.objects.get(id=profile_id)
        except MappingProfile.DoesNotExist:
            messages.error(request, "Invalid mapping profile.")
            return redirect('category_training_upload')
        
        # Parse CSV and extract unique patterns
        parsed_file = StringIO(file_content)
        patterns = self.extract_unique_patterns(parsed_file, profile)
        
        # Store patterns in session for training (ensure JSON serializable)
        serializable_patterns = self.make_patterns_serializable(patterns)
        request.session['training_patterns'] = serializable_patterns
        request.session['current_pattern_index'] = 0
        
        return render(request, self.template_name, {
            'filename': filename,
            'total_patterns': len(patterns),
            'patterns_preview': patterns[:5]  # Show first 5 for preview
        })

    def extract_unique_patterns(self, file_handle, profile):
        """Extract unique transaction patterns from CSV for training."""
        file_handle.seek(0)
        
        # Group transactions by description patterns
        pattern_groups = defaultdict(list)
        
        try:
            from ingest.services.mapping import map_row_with_profile
            reader = csv.DictReader(file_handle)
            
            for row_data in reader:
                try:
                    # Map the row using the profile
                    mapped = map_row_with_profile(row_data, profile)
                    
                    if mapped.get('description'):
                        description = mapped['description'].strip()
                        amount = mapped.get('amount', 0)
                        
                        # Create a pattern key based on description similarity
                        pattern_key = self.create_pattern_key(description)
                        
                        pattern_groups[pattern_key].append({
                            'description': description,
                            'amount': amount,
                            'raw_row': row_data,
                            'mapped': mapped
                        })
                        
                except Exception as e:
                    logger.warning(f"Error processing row: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error reading CSV: {e}")
            return []
        
        # Convert to training patterns with AI suggestions
        training_patterns = []
        for pattern_key, transactions in pattern_groups.items():
            if len(transactions) > 0:
                # Use the first transaction as representative
                representative = transactions[0]
                
                # Get AI suggestions with reasoning
                suggested_category, suggested_subcategory, reasoning = categorize_transaction_with_reasoning(
                    representative['description'], 
                    float(representative['amount']) if representative['amount'] else 0
                )
                
                training_patterns.append({
                    'pattern_key': pattern_key,
                    'representative_description': representative['description'],
                    'representative_amount': representative['amount'],
                    'transaction_count': len(transactions),
                    'transactions': transactions[:3],  # Keep first 3 examples
                    'suggested_category': suggested_category,
                    'suggested_subcategory': suggested_subcategory,
                    'reasoning': reasoning,
                    'confirmed_category': None,
                    'confirmed_subcategory': None,
                    'confirmed_payoree': None
                })
        
        # Sort by transaction count (most common patterns first)
        training_patterns.sort(key=lambda x: x['transaction_count'], reverse=True)
        return training_patterns

    def make_patterns_serializable(self, patterns):
        """Convert patterns to JSON-serializable format by handling dates and other objects."""
        import datetime
        import decimal
        
        def serialize_value(value):
            """Recursively serialize any value to be JSON-compatible."""
            if isinstance(value, datetime.date):
                return value.isoformat()
            elif isinstance(value, datetime.datetime):
                return value.isoformat()
            elif isinstance(value, decimal.Decimal):
                return float(value)
            elif isinstance(value, dict):
                return {k: serialize_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [serialize_value(item) for item in value]
            elif isinstance(value, tuple):
                return [serialize_value(item) for item in value]
            else:
                return value
        
        return serialize_value(patterns)

    def create_pattern_key(self, description):
        """Create a pattern key for grouping similar transactions."""
        import re
        
        # Normalize description for pattern matching
        pattern = description.upper()
        
        # Remove common transaction noise
        pattern = re.sub(r'\d{4,}', 'XXXX', pattern)  # Replace long numbers
        pattern = re.sub(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b', 'DATE', pattern)  # Replace dates
        pattern = re.sub(r'\$[\d,]+\.?\d*', 'AMOUNT', pattern)  # Replace amounts
        pattern = re.sub(r'\s+', ' ', pattern).strip()  # Normalize whitespace
        
        # Extract merchant/key part (first few meaningful words)
        words = pattern.split()[:3]  # Take first 3 words as pattern
        return ' '.join(words)


class CategoryTrainingSessionView(View):
    """Interactive training session for confirming/correcting categorizations."""
    template_name = "transactions/category_training_session.html"

    @method_decorator(trace)
    def get(self, request):
        # Get current pattern from session
        try:
            patterns = request.session['training_patterns']
            current_index = request.session.get('current_pattern_index', 0)
        except KeyError:
            messages.error(request, "No training session found. Please upload a CSV first.")
            return redirect('category_training_upload')
        
        if current_index >= len(patterns):
            # Training complete
            return redirect('category_training_complete')
        
        current_pattern = patterns[current_index]
        
        # Get available categories for selection
        top_level_categories = Category.objects.filter(parent=None).prefetch_related('subcategories')
        payorees = Payoree.objects.order_by('name')
        
        # Calculate progress
        progress_percentage = ((current_index + 1) / len(patterns)) * 100
        
        return render(request, self.template_name, {
            'pattern': current_pattern,
            'current_index': current_index + 1,
            'total_patterns': len(patterns),
            'progress_percentage': progress_percentage,
            'top_level_categories': top_level_categories,
            'payorees': payorees
        })

    @method_decorator(trace)
    def post(self, request):
        try:
            patterns = request.session['training_patterns']
            current_index = request.session.get('current_pattern_index', 0)
        except KeyError:
            messages.error(request, "Training session expired.")
            return redirect('category_training_upload')
        
        if current_index >= len(patterns):
            return redirect('category_training_complete')
        
        # Process user's categorization choices
        category_id = request.POST.get('category')
        subcategory_id = request.POST.get('subcategory')
        payoree_id = request.POST.get('payoree')
        new_category_name = request.POST.get('new_category', '').strip()
        new_subcategory_name = request.POST.get('new_subcategory', '').strip()
        new_payoree_name = request.POST.get('new_payoree', '').strip()
        action = request.POST.get('action', 'next')
        
        # Update current pattern with user's choices
        current_pattern = patterns[current_index]
        
        # Handle category creation/selection
        if category_id == '__new__' and new_category_name:
            # Create new category
            category, created = Category.objects.get_or_create(
                name=new_category_name,
                defaults={'parent': None}
            )
            current_pattern['confirmed_category'] = category.name
            current_pattern['confirmed_category_id'] = category.id
            if created:
                messages.success(request, f"Created new category: {category.name}")
        elif category_id:
            try:
                category = Category.objects.get(id=category_id)
                current_pattern['confirmed_category'] = category.name
                current_pattern['confirmed_category_id'] = category.id
            except Category.DoesNotExist:
                pass
        
        # Handle subcategory creation/selection
        if subcategory_id == '__new__' and new_subcategory_name:
            # Create new subcategory under the selected/created category
            parent_category = None
            if category_id == '__new__' and new_category_name:
                parent_category = Category.objects.get(name=new_category_name)
            elif category_id:
                try:
                    parent_category = Category.objects.get(id=category_id)
                except Category.DoesNotExist:
                    pass
            
            if parent_category:
                subcategory, created = Category.objects.get_or_create(
                    name=new_subcategory_name,
                    parent=parent_category
                )
                current_pattern['confirmed_subcategory'] = subcategory.name
                current_pattern['confirmed_subcategory_id'] = subcategory.id
                if created:
                    messages.success(request, f"Created new subcategory: {subcategory.name}")
            else:
                messages.error(request, "Cannot create subcategory without a parent category.")
        elif subcategory_id:
            try:
                subcategory = Category.objects.get(id=subcategory_id)
                current_pattern['confirmed_subcategory'] = subcategory.name
                current_pattern['confirmed_subcategory_id'] = subcategory.id
            except Category.DoesNotExist:
                pass
        
        # Handle payoree creation/selection
        if payoree_id == '__new__' and new_payoree_name:
            # Create new payoree
            payoree, created = Payoree.objects.get_or_create(
                name=new_payoree_name
            )
            current_pattern['confirmed_payoree'] = payoree.name
            current_pattern['confirmed_payoree_id'] = payoree.id
            if created:
                messages.success(request, f"Created new payoree: {payoree.name}")
        elif payoree_id:
            try:
                payoree = Payoree.objects.get(id=payoree_id)
                current_pattern['confirmed_payoree'] = payoree.name
                current_pattern['confirmed_payoree_id'] = payoree.id
            except Payoree.DoesNotExist:
                pass
        
        # Save learning data if user provided corrections
        if action == 'save_and_next' and (category_id or subcategory_id or payoree_id):
            self.save_learning_data(current_pattern)
        
        # Move to next pattern or handle navigation
        if action == 'skip':
            request.session['current_pattern_index'] = current_index + 1
        elif action in ['next', 'save_and_next']:
            request.session['current_pattern_index'] = current_index + 1
        elif action == 'previous' and current_index > 0:
            request.session['current_pattern_index'] = current_index - 1
        
        # Update the pattern in session
        patterns[current_index] = current_pattern
        request.session['training_patterns'] = patterns
        
        return redirect('category_training_session')

    def save_learning_data(self, pattern):
        """Save the user's categorization as learning data."""
        try:
            # Save subcategory learning
            if pattern.get('confirmed_subcategory_id'):
                try:
                    subcategory = Category.objects.get(id=pattern['confirmed_subcategory_id'])
                    learned, created = LearnedSubcat.objects.get_or_create(
                        key=pattern['pattern_key'],
                        subcategory=subcategory,
                        defaults={'count': 1}
                    )
                    if not created:
                        learned.count += 1
                        learned.save()
                    logger.info(f"Saved subcategory learning: {pattern['pattern_key']} -> {subcategory.name}")
                except Category.DoesNotExist:
                    logger.warning(f"Subcategory {pattern['confirmed_subcategory_id']} not found")
            
            # Save payoree learning
            if pattern.get('confirmed_payoree_id'):
                try:
                    payoree = Payoree.objects.get(id=pattern['confirmed_payoree_id'])
                    learned, created = LearnedPayoree.objects.get_or_create(
                        key=pattern['pattern_key'],
                        payoree=payoree,
                        defaults={'count': 1}
                    )
                    if not created:
                        learned.count += 1
                        learned.save()
                    logger.info(f"Saved payoree learning: {pattern['pattern_key']} -> {payoree.name}")
                except Payoree.DoesNotExist:
                    logger.warning(f"Payoree {pattern['confirmed_payoree_id']} not found")
                
        except Exception as e:
            logger.error(f"Error saving learning data: {e}")


class CategoryTrainingCompleteView(View):
    """Show training completion summary and statistics."""
    template_name = "transactions/category_training_complete.html"

    @method_decorator(trace)
    def get(self, request):
        # Get training results from session
        try:
            patterns = request.session['training_patterns']
            filename = request.session.get('training_filename', 'Unknown')
        except KeyError:
            messages.error(request, "No training session found.")
            return redirect('category_training_upload')
        
        # Calculate statistics
        total_patterns = len(patterns)
        confirmed_patterns = sum(1 for p in patterns if p.get('confirmed_category') or p.get('confirmed_subcategory'))
        skipped_patterns = total_patterns - confirmed_patterns
        
        # Get patterns that were confirmed
        confirmed_list = [p for p in patterns if p.get('confirmed_category') or p.get('confirmed_subcategory')]
        
        # Clear session data
        request.session.pop('training_patterns', None)
        request.session.pop('current_pattern_index', None)
        request.session.pop('training_file', None)
        request.session.pop('training_profile_id', None)
        request.session.pop('training_filename', None)
        
        return render(request, self.template_name, {
            'filename': filename,
            'total_patterns': total_patterns,
            'confirmed_patterns': confirmed_patterns,
            'skipped_patterns': skipped_patterns,
            'confirmation_rate': (confirmed_patterns / total_patterns * 100) if total_patterns > 0 else 0,
            'confirmed_list': confirmed_list[:10]  # Show first 10 confirmed patterns
        })


class LearnFromCurrentView(View):
    """Allow users to teach the AI from existing correct categorizations."""
    
    @method_decorator(trace)
    def post(self, request, transaction_id):
        """Learn from the current categorization of a transaction."""
        try:
            transaction = get_object_or_404(Transaction, id=transaction_id)
            
            # Validate that the transaction has proper categorization
            if not transaction.category and not transaction.subcategory and not transaction.payoree:
                return JsonResponse({
                    'success': False,
                    'message': 'Transaction has no categorization to learn from.'
                })
            
            # Create pattern key for learning
            pattern_key = self.create_pattern_key(transaction.description)
            
            learned_count = 0
            
            # Learn subcategory if available
            if transaction.subcategory:
                learned, created = LearnedSubcat.objects.get_or_create(
                    key=pattern_key,
                    subcategory=transaction.subcategory,
                    defaults={'count': 1}
                )
                if not created:
                    learned.count += 1
                    learned.save()
                learned_count += 1
                logger.info(f"Learned subcategory: {pattern_key} -> {transaction.subcategory.name}")
            
            # Learn payoree if available  
            if transaction.payoree:
                learned, created = LearnedPayoree.objects.get_or_create(
                    key=pattern_key,
                    payoree=transaction.payoree,
                    defaults={'count': 1}
                )
                if not created:
                    learned.count += 1
                    learned.save()
                learned_count += 1
                logger.info(f"Learned payoree: {pattern_key} -> {transaction.payoree.name}")
            
            if learned_count > 0:
                return JsonResponse({
                    'success': True,
                    'message': f'Successfully learned from current assignment. The AI will now better recognize similar transactions.',
                    'learned_items': learned_count
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'No categorization data available to learn from.'
                })
                
        except Exception as e:
            logger.error(f"Error learning from current assignment: {e}")
            return JsonResponse({
                'success': False,
                'message': 'An error occurred while learning from this transaction.'
            })
    
    def create_pattern_key(self, description):
        """Create a pattern key for grouping similar transactions."""
        import re
        
        # Normalize description for pattern matching
        pattern = description.upper()
        
        # Remove common transaction noise
        pattern = re.sub(r'\d{4,}', 'XXXX', pattern)  # Replace long numbers
        pattern = re.sub(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b', 'DATE', pattern)  # Replace dates
        pattern = re.sub(r'\$[\d,]+\.?\d*', 'AMOUNT', pattern)  # Replace amounts
        pattern = re.sub(r'\s+', ' ', pattern).strip()  # Normalize whitespace
        
        # Extract merchant/key part (first few meaningful words)
        words = pattern.split()[:3]  # Take first 3 words as pattern
        return ' '.join(words)
