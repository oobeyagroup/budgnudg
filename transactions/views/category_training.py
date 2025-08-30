# transactions/views/category_training.py
from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.db import transaction as db_transaction
from django.utils import timezone
from transactions.models import (
    Transaction,
    Category,
    Payoree,
    LearnedSubcat,
    LearnedPayoree,
    KeywordRule,
)
from transactions.forms import TransactionImportForm
from transactions.utils import trace, read_uploaded_file
from transactions.categorization import (
    categorize_transaction,
    suggest_subcategory,
    categorize_transaction_with_reasoning,
)
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
        from ingest.models import FinancialAccount

        # Get available mapping profiles
        profiles = FinancialAccount.objects.all()
        profile_choices = [(p.id, p.name) for p in profiles]

        form = TransactionImportForm(
            profile_choices=profile_choices,
            account_choices=[
                ("training", "Training Data")
            ],  # Dummy account for training
        )

        return render(
            request,
            self.template_name,
            {"form": form, "title": "Category Training - Upload CSV"},
        )

    @method_decorator(trace)
    def post(self, request):
        from ingest.models import FinancialAccount

        logger.info("CategoryTrainingUploadView POST request received")

        profiles = FinancialAccount.objects.all()
        profile_choices = [(p.id, p.name) for p in profiles]

        form = TransactionImportForm(
            request.POST,
            request.FILES,
            profile_choices=profile_choices,
            account_choices=[("training", "Training Data")],
        )

        logger.info(f"Form is_valid: {form.is_valid()}")
        if not form.is_valid():
            logger.error(f"Form errors: {form.errors}")

        if form.is_valid():
            file = request.FILES["file"]
            profile_id = form.cleaned_data["mapping_profile"]

            try:
                profile = FinancialAccount.objects.get(id=profile_id)
            except FinancialAccount.DoesNotExist:
                messages.error(request, "Invalid mapping profile selected.")
                return render(request, self.template_name, {"form": form})

            # Store in session for training analysis
            request.session["training_file"] = read_uploaded_file(file)
            request.session["training_profile_id"] = profile_id
            request.session["training_filename"] = file.name

            return redirect("transactions:category_training_analyze")

        return render(
            request,
            self.template_name,
            {"form": form, "title": "Category Training - Upload CSV"},
        )


class CategoryTrainingAnalyzeView(View):
    """Analyze uploaded CSV and extract unique transaction patterns for training."""

    template_name = "transactions/category_training_analyze.html"

    @method_decorator(trace)
    def get(self, request):
        # Retrieve upload data from session
        try:
            file_content = request.session["training_file"]
            profile_id = request.session["training_profile_id"]
            filename = request.session["training_filename"]
        except KeyError:
            messages.error(
                request, "No training file found. Please upload a CSV first."
            )
            return redirect("transactions:category_training_upload")

        from ingest.models import FinancialAccount

        try:
            profile = FinancialAccount.objects.get(id=profile_id)
        except FinancialAccount.DoesNotExist:
            messages.error(request, "Invalid mapping profile.")
            return redirect("transactions:category_training_upload")

        # Parse CSV and extract unique patterns
        parsed_file = StringIO(file_content)
        patterns = self.extract_unique_patterns(parsed_file, profile)

        # Store patterns in session for training (ensure JSON serializable)
        serializable_patterns = self.make_patterns_serializable(patterns)
        request.session["training_patterns"] = serializable_patterns
        request.session["current_pattern_index"] = 0

        return render(
            request,
            self.template_name,
            {
                "filename": filename,
                "total_patterns": len(patterns),
                "patterns_preview": patterns[:5],  # Show first 5 for preview
            },
        )

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

                    if mapped.get("description"):
                        description = mapped["description"].strip()
                        amount = mapped.get("amount", 0)

                        # Create a pattern key based on description similarity
                        pattern_key = self.create_pattern_key(description)

                        pattern_groups[pattern_key].append(
                            {
                                "description": description,
                                "amount": amount,
                                "raw_row": row_data,
                                "mapped": mapped,
                            }
                        )

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
                suggested_category, suggested_subcategory, reasoning = (
                    categorize_transaction_with_reasoning(
                        representative["description"],
                        (
                            float(representative["amount"])
                            if representative["amount"]
                            else 0
                        ),
                    )
                )

                training_patterns.append(
                    {
                        "pattern_key": pattern_key,
                        "representative_description": representative["description"],
                        "representative_amount": representative["amount"],
                        "transaction_count": len(transactions),
                        "transactions": transactions[:3],  # Keep first 3 examples
                        "suggested_category": suggested_category,
                        "suggested_subcategory": suggested_subcategory,
                        "reasoning": reasoning,
                        "confirmed_category": None,
                        "confirmed_subcategory": None,
                        "confirmed_payoree": None,
                    }
                )

        # Sort by transaction count (most common patterns first)
        training_patterns.sort(key=lambda x: x["transaction_count"], reverse=True)
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
        pattern = re.sub(r"\d{4,}", "XXXX", pattern)  # Replace long numbers
        pattern = re.sub(
            r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", "DATE", pattern
        )  # Replace dates
        pattern = re.sub(r"\$[\d,]+\.?\d*", "AMOUNT", pattern)  # Replace amounts
        pattern = re.sub(r"\s+", " ", pattern).strip()  # Normalize whitespace

        # Extract merchant/key part (first few meaningful words)
        words = pattern.split()[:3]  # Take first 3 words as pattern
        return " ".join(words)


class CategoryTrainingSessionView(View):
    """Interactive training session for confirming/correcting categorizations."""

    template_name = "transactions/category_training_session.html"

    @method_decorator(trace)
    def get(self, request):
        # Get current pattern from session
        try:
            patterns = request.session["training_patterns"]
            current_index = request.session.get("current_pattern_index", 0)
        except KeyError:
            messages.error(
                request, "No training session found. Please upload a CSV first."
            )
            return redirect("transactions:category_training_upload")

        if current_index >= len(patterns):
            # Training complete
            return redirect("transactions:category_training_complete")

        current_pattern = patterns[current_index]

        # Enhanced pattern analysis
        description = current_pattern["representative_description"]

        # Extract merchant for training insight
        from transactions.categorization import extract_merchant_from_description

        extracted_merchant = extract_merchant_from_description(description)
        current_pattern["extracted_merchant"] = extracted_merchant

        # Identify potential keywords for rule creation
        potential_keywords = self.identify_potential_keywords(description)
        current_pattern["potential_keywords"] = potential_keywords

        # Check existing learned patterns to show user what already exists
        current_pattern["existing_merchant_patterns"] = (
            self.get_existing_patterns(extracted_merchant) if extracted_merchant else {}
        )
        current_pattern["existing_description_patterns"] = self.get_existing_patterns(
            description
        )

        # Get available categories for selection
        top_level_categories = Category.objects.filter(parent=None).prefetch_related(
            "subcategories"
        )
        payorees = Payoree.objects.order_by("name")

        # Calculate progress
        progress_percentage = ((current_index + 1) / len(patterns)) * 100

        # Prepare enhanced training interface data
        potential_keywords = current_pattern.get("potential_keywords", [])
        existing_patterns = {
            "merchant": current_pattern.get("existing_merchant_patterns", {}).get(
                "merchant", []
            ),
            "description": current_pattern.get("existing_description_patterns", {}).get(
                "description", []
            ),
            "keywords": current_pattern.get("existing_description_patterns", {}).get(
                "keywords", []
            ),
        }

        return render(
            request,
            self.template_name,
            {
                "pattern": current_pattern,
                "current_index": current_index + 1,
                "total_patterns": len(patterns),
                "progress_percentage": progress_percentage,
                "top_level_categories": top_level_categories,
                "payorees": payorees,
                "potential_keywords": potential_keywords,
                "existing_patterns": existing_patterns,
            },
        )

    def identify_potential_keywords(self, description):
        """Identify potential keywords that could be used for rules."""
        import re

        keywords = []

        # Common patterns that make good keywords
        patterns = [
            r"\b(DIRECT DEP|DIRECTDEP|DIRECT DEPOSIT)\b",
            r"\b(ATM|WITHDRAWAL|DEPOSIT)\b",
            r"\b([A-Z\s]+CO|[A-Z\s]+CORP|[A-Z\s]+INC|[A-Z\s]+LLC)\b",
            r"\b(BILL|PAYMENT|PYMT|PMT)\b",
            r"\b(TRANSFER|XFER)\b",
            r"\b(REFUND|RETURN)\b",
            r"\b(FEE|CHARGE)\b",
            r"\b(CHECK|CHK)\b",
            r"\b([A-Z]{3,}\s+[A-Z]{3,})\b",  # Multi-word caps like "MOBILE DEPOSIT"
        ]

        description_upper = description.upper()
        for pattern in patterns:
            matches = re.findall(pattern, description_upper)
            for match in matches:
                if isinstance(match, tuple):
                    # Handle groups in regex
                    for group in match:
                        if group and len(group.strip()) >= 3:
                            keywords.append(group.strip())
                else:
                    if len(match.strip()) >= 3:
                        keywords.append(match.strip())

        # Remove duplicates and filter out overly generic terms
        filtered_keywords = []
        generic_terms = {"THE", "AND", "FOR", "WITH", "FROM", "TO"}

        for keyword in set(keywords):
            if keyword not in generic_terms and len(keyword) >= 3:
                filtered_keywords.append(keyword)

        return sorted(filtered_keywords)[:5]  # Limit to top 5 suggestions

    def get_existing_patterns(self, key):
        """Get existing learned patterns for this key."""
        from transactions.models import LearnedSubcat, LearnedPayoree

        if not key:
            return {"subcategories": [], "payorees": []}

        try:
            subcats = (
                LearnedSubcat.objects.filter(key=key)
                .select_related("subcategory")
                .values("subcategory__name", "count", "last_seen")[:5]
            )  # Limit to top 5

            payorees = (
                LearnedPayoree.objects.filter(key=key)
                .select_related("payoree")
                .values("payoree__name", "count", "last_seen")[:5]
            )  # Limit to top 5

            return {"subcategories": list(subcats), "payorees": list(payorees)}
        except Exception as e:
            logger.warning(f"Error getting existing patterns for key '{key}': {e}")
            return {"subcategories": [], "payorees": []}

    @method_decorator(trace)
    def post(self, request):
        try:
            patterns = request.session["training_patterns"]
            current_index = request.session.get("current_pattern_index", 0)
        except KeyError:
            messages.error(request, "Training session expired.")
            return redirect("transactions:category_training_upload")

        if current_index >= len(patterns):
            return redirect("transactions:category_training_complete")

        # Process user's categorization choices
        category_id = request.POST.get("category")
        subcategory_id = request.POST.get("subcategory")
        payoree_id = request.POST.get("payoree")
        new_category_name = request.POST.get("new_category", "").strip()
        new_subcategory_name = request.POST.get("new_subcategory", "").strip()
        new_payoree_name = request.POST.get("new_payoree", "").strip()
        action = request.POST.get("action", "next")

        # Enhanced training options
        keyword_rule_text = request.POST.get("keyword_rule_text", "").strip()
        keyword_rule_priority = int(request.POST.get("keyword_rule_priority", 100))
        create_keyword_rule = request.POST.get("create_keyword_rule") in ("on", "1")
        train_merchant_pattern = request.POST.get("train_merchant_pattern") == "on"
        train_description_pattern = (
            request.POST.get("train_description_pattern") == "on"
        )

        # Update current pattern with user's choices
        current_pattern = patterns[current_index]

        # Handle category creation/selection
        if category_id == "__new__" and new_category_name:
            # Create new category
            category, created = Category.objects.get_or_create(
                name=new_category_name, defaults={"parent": None}
            )
            current_pattern["confirmed_category"] = category.name
            current_pattern["confirmed_category_id"] = category.id
            if created:
                messages.success(request, f"Created new category: {category.name}")
        elif category_id:
            try:
                category = Category.objects.get(id=category_id)
                current_pattern["confirmed_category"] = category.name
                current_pattern["confirmed_category_id"] = category.id
            except Category.DoesNotExist:
                pass

        # Handle subcategory creation/selection
        if subcategory_id == "__new__" and new_subcategory_name:
            # Create new subcategory under the selected/created category
            parent_category = None
            if category_id == "__new__" and new_category_name:
                parent_category = Category.objects.get(name=new_category_name)
            elif category_id:
                try:
                    parent_category = Category.objects.get(id=category_id)
                except Category.DoesNotExist:
                    pass

            if parent_category:
                subcategory, created = Category.objects.get_or_create(
                    name=new_subcategory_name, parent=parent_category
                )
                current_pattern["confirmed_subcategory"] = subcategory.name
                current_pattern["confirmed_subcategory_id"] = subcategory.id
                if created:
                    messages.success(
                        request, f"Created new subcategory: {subcategory.name}"
                    )
            else:
                messages.error(
                    request, "Cannot create subcategory without a parent category."
                )
        elif subcategory_id:
            try:
                subcategory = Category.objects.get(id=subcategory_id)
                current_pattern["confirmed_subcategory"] = subcategory.name
                current_pattern["confirmed_subcategory_id"] = subcategory.id
            except Category.DoesNotExist:
                pass

        # Handle payoree creation/selection
        if payoree_id == "__new__" and new_payoree_name:
            # Create new payoree
            payoree, created = Payoree.objects.get_or_create(name=new_payoree_name)
            current_pattern["confirmed_payoree"] = payoree.name
            current_pattern["confirmed_payoree_id"] = payoree.id
            if created:
                messages.success(request, f"Created new payoree: {payoree.name}")
        elif payoree_id:
            try:
                payoree = Payoree.objects.get(id=payoree_id)
                current_pattern["confirmed_payoree"] = payoree.name
                current_pattern["confirmed_payoree_id"] = payoree.id
            except Payoree.DoesNotExist:
                pass

        # Enhanced training features - execute if user wants to save
        if action == "save_and_next":
            # Get the selected/created category and subcategory objects for training
            selected_category = None
            selected_subcategory = None
            selected_payoree = None

            # Get category object
            if category_id == "__new__" and new_category_name:
                selected_category = Category.objects.get(name=new_category_name)
            elif category_id:
                try:
                    selected_category = Category.objects.get(id=category_id)
                except Category.DoesNotExist:
                    pass

            # Get subcategory object
            if (
                subcategory_id == "__new__"
                and new_subcategory_name
                and selected_category
            ):
                selected_subcategory = Category.objects.get(
                    name=new_subcategory_name, parent=selected_category
                )
            elif subcategory_id:
                try:
                    selected_subcategory = Category.objects.get(id=subcategory_id)
                except Category.DoesNotExist:
                    pass

            # Get payoree object
            if payoree_id == "__new__" and new_payoree_name:
                selected_payoree = Payoree.objects.get(name=new_payoree_name)
            elif payoree_id == "__suggested__" and current_pattern.get(
                "extracted_merchant"
            ):
                selected_payoree, _ = Payoree.objects.get_or_create(
                    name=current_pattern["extracted_merchant"]
                )
            elif payoree_id:
                try:
                    selected_payoree = Payoree.objects.get(id=payoree_id)
                except Payoree.DoesNotExist:
                    pass

            # Method 1: Create Keyword Rule (Highest Priority)
            if create_keyword_rule and keyword_rule_text and selected_category:
                try:
                    rule, created = KeywordRule.objects.get_or_create(
                        keyword=keyword_rule_text,
                        category=selected_category,
                        subcategory=selected_subcategory,
                        defaults={
                            "priority": keyword_rule_priority,
                            "is_active": True,
                            "created_by_user": True,
                        },
                    )
                    if created:
                        messages.success(
                            request,
                            f'✅ Created keyword rule: "{keyword_rule_text}" → {selected_category.name}'
                            + (
                                f"/{selected_subcategory.name}"
                                if selected_subcategory
                                else ""
                            ),
                        )
                    else:
                        messages.info(
                            request,
                            f'ℹ️ Keyword rule already exists: "{keyword_rule_text}"',
                        )
                except Exception as e:
                    messages.error(request, f"❌ Error creating keyword rule: {e}")

            # Method 2: Train Merchant Pattern
            if (
                train_merchant_pattern
                and current_pattern.get("extracted_merchant")
                and selected_subcategory
            ):
                try:
                    merchant_key = current_pattern["extracted_merchant"]
                    learned, created = LearnedSubcat.objects.get_or_create(
                        key=merchant_key,
                        subcategory=selected_subcategory,
                        defaults={"count": 1},
                    )
                    if not created:
                        learned.count += 1
                        learned.save()

                    # Also train payoree if provided
                    if selected_payoree:
                        learned_payoree, created = LearnedPayoree.objects.get_or_create(
                            key=merchant_key,
                            payoree=selected_payoree,
                            defaults={"count": 1},
                        )
                        if not created:
                            learned_payoree.count += 1
                            learned_payoree.save()

                    messages.success(
                        request,
                        f'🏪 Trained merchant pattern: "{merchant_key}" → {selected_subcategory.name}',
                    )
                except Exception as e:
                    messages.error(request, f"❌ Error training merchant pattern: {e}")

            # Method 3: Train Description Pattern
            if train_description_pattern and selected_subcategory:
                try:
                    description_key = current_pattern["pattern_key"]
                    learned, created = LearnedSubcat.objects.get_or_create(
                        key=description_key,
                        subcategory=selected_subcategory,
                        defaults={"count": 1},
                    )
                    if not created:
                        learned.count += 1
                        learned.save()

                    # Also train payoree if provided
                    if selected_payoree:
                        learned_payoree, created = LearnedPayoree.objects.get_or_create(
                            key=description_key,
                            payoree=selected_payoree,
                            defaults={"count": 1},
                        )
                        if not created:
                            learned_payoree.count += 1
                            learned_payoree.save()

                    messages.success(
                        request,
                        f'📝 Trained description pattern: "{description_key}" → {selected_subcategory.name}',
                    )
                except Exception as e:
                    messages.error(
                        request, f"❌ Error training description pattern: {e}"
                    )

        # Save learning data if user provided corrections (legacy method - still needed for backward compatibility)
        if action == "save_and_next" and (category_id or subcategory_id or payoree_id):
            self.save_learning_data(current_pattern)

        # Move to next pattern or handle navigation
        if action == "skip":
            request.session["current_pattern_index"] = current_index + 1
        elif action in ["next", "save_and_next"]:
            request.session["current_pattern_index"] = current_index + 1
        elif action == "previous" and current_index > 0:
            request.session["current_pattern_index"] = current_index - 1

        # Update the pattern in session
        patterns[current_index] = current_pattern
        request.session["training_patterns"] = patterns

        return redirect("transactions:category_training_session")

    def save_learning_data(self, pattern):
        """Save the user's categorization as learning data."""
        try:
            # Save subcategory learning
            if pattern.get("confirmed_subcategory_id"):
                try:
                    subcategory = Category.objects.get(
                        id=pattern["confirmed_subcategory_id"]
                    )
                    learned, created = LearnedSubcat.objects.get_or_create(
                        key=pattern["pattern_key"],
                        subcategory=subcategory,
                        defaults={"count": 1},
                    )
                    if not created:
                        learned.count += 1
                        learned.save()
                    logger.info(
                        f"Saved subcategory learning: {pattern['pattern_key']} -> {subcategory.name}"
                    )
                except Category.DoesNotExist:
                    logger.warning(
                        f"Subcategory {pattern['confirmed_subcategory_id']} not found"
                    )

            # Save payoree learning
            if pattern.get("confirmed_payoree_id"):
                try:
                    payoree = Payoree.objects.get(id=pattern["confirmed_payoree_id"])
                    learned, created = LearnedPayoree.objects.get_or_create(
                        key=pattern["pattern_key"],
                        payoree=payoree,
                        defaults={"count": 1},
                    )
                    if not created:
                        learned.count += 1
                        learned.save()
                    logger.info(
                        f"Saved payoree learning: {pattern['pattern_key']} -> {payoree.name}"
                    )
                except Payoree.DoesNotExist:
                    logger.warning(
                        f"Payoree {pattern['confirmed_payoree_id']} not found"
                    )

        except Exception as e:
            logger.error(f"Error saving learning data: {e}")


class CategoryTrainingCompleteView(View):
    """Show training completion summary and statistics."""

    template_name = "transactions/category_training_complete.html"

    @method_decorator(trace)
    def get(self, request):
        # Get training results from session
        try:
            patterns = request.session["training_patterns"]
            filename = request.session.get("training_filename", "Unknown")
        except KeyError:
            messages.error(request, "No training session found.")
            return redirect("transactions:category_training_upload")

        # Calculate statistics
        total_patterns = len(patterns)
        confirmed_patterns = sum(
            1
            for p in patterns
            if p.get("confirmed_category") or p.get("confirmed_subcategory")
        )
        skipped_patterns = total_patterns - confirmed_patterns

        # Get patterns that were confirmed
        confirmed_list = [
            p
            for p in patterns
            if p.get("confirmed_category") or p.get("confirmed_subcategory")
        ]

        # Clear session data
        request.session.pop("training_patterns", None)
        request.session.pop("current_pattern_index", None)
        request.session.pop("training_file", None)
        request.session.pop("training_profile_id", None)
        request.session.pop("training_filename", None)

        return render(
            request,
            self.template_name,
            {
                "filename": filename,
                "total_patterns": total_patterns,
                "confirmed_patterns": confirmed_patterns,
                "skipped_patterns": skipped_patterns,
                "confirmation_rate": (
                    (confirmed_patterns / total_patterns * 100)
                    if total_patterns > 0
                    else 0
                ),
                "confirmed_list": confirmed_list[
                    :10
                ],  # Show first 10 confirmed patterns
            },
        )


class LearnFromCurrentView(View):
    """Allow users to teach the AI from existing correct categorizations."""

    @method_decorator(trace)
    def post(self, request, transaction_id):
        """Learn from the current categorization of a transaction."""
        from ..categorization import extract_merchant_from_description

        try:
            transaction = get_object_or_404(Transaction, id=transaction_id)

            # Validate that the transaction has proper categorization
            if (
                not transaction.category
                and not transaction.subcategory
                and not transaction.payoree
            ):
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Transaction has no categorization to learn from.",
                    }
                )

            # Create multiple pattern keys for better learning
            merchant_key = extract_merchant_from_description(transaction.description)
            original_key = transaction.description.upper().strip()
            pattern_key = self.create_pattern_key(transaction.description)

            # Use a list of keys to try, starting with most specific
            learning_keys = [original_key, merchant_key, pattern_key]
            # Remove duplicates while preserving order
            learning_keys = list(dict.fromkeys(learning_keys))

            learned_count = 0

            # Learn subcategory if available - use the merchant key primarily
            if transaction.subcategory:
                primary_key = merchant_key if merchant_key else original_key
                learned, created = LearnedSubcat.objects.get_or_create(
                    key=primary_key,
                    subcategory=transaction.subcategory,
                    defaults={"count": 1},
                )
                if not created:
                    learned.count += 1
                    learned.save()
                learned_count += 1
                logger.info(
                    f"Learned subcategory: {primary_key} -> {transaction.subcategory.name}"
                )

            # Learn payoree if available
            if transaction.payoree:
                primary_key = merchant_key if merchant_key else original_key
                learned, created = LearnedPayoree.objects.get_or_create(
                    key=primary_key, payoree=transaction.payoree, defaults={"count": 1}
                )
                if not created:
                    learned.count += 1
                    learned.save()
                learned_count += 1
                logger.info(
                    f"Learned payoree: {primary_key} -> {transaction.payoree.name}"
                )

            if learned_count > 0:
                return JsonResponse(
                    {
                        "success": True,
                        "message": f"Successfully learned from current assignment. The AI will now better recognize similar transactions.",
                        "learned_items": learned_count,
                    }
                )
            else:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "No categorization data available to learn from.",
                    }
                )

        except Exception as e:
            logger.error(f"Error learning from current assignment: {e}")
            return JsonResponse(
                {
                    "success": False,
                    "message": "An error occurred while learning from this transaction.",
                }
            )

    def create_pattern_key(self, description):
        """Create a pattern key for grouping similar transactions."""
        import re

        # Use the same logic as extract_merchant_from_description for consistency
        from ..categorization import extract_merchant_from_description

        # Try to extract the core merchant name first
        merchant = extract_merchant_from_description(description)

        # For learning, we want to use shorter, more generic keys that will match future transactions
        # If the merchant extraction returned something meaningful and not too long
        if merchant and len(merchant.split()) <= 4:
            return merchant

        # Fallback: create a normalized pattern from the description
        pattern = description.upper()

        # Remove common transaction noise
        pattern = re.sub(r"\d{4,}", "", pattern)  # Remove long numbers
        pattern = re.sub(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", "", pattern)  # Remove dates
        pattern = re.sub(r"\$[\d,]+\.?\d*", "", pattern)  # Remove amounts
        pattern = re.sub(r"PPD\s*ID:\s*\d+", "", pattern)  # Remove PPD IDs
        pattern = re.sub(r"WEB\s*ID:\s*\d+", "", pattern)  # Remove WEB IDs
        pattern = re.sub(r"\s+", " ", pattern).strip()  # Normalize whitespace

        # Extract key words (usually the first few meaningful words)
        words = [w for w in pattern.split() if len(w) > 2]  # Skip short words
        return " ".join(words[:3])  # Take first 3 meaningful words


class KeywordRulesView(View):
    """Manage keyword-based categorization rules."""

    template_name = "transactions/keyword_rules.html"

    @method_decorator(trace)
    def get(self, request):
        """Display keyword rules management interface."""
        from ..models import KeywordRule, Category
        import json

        # Get all keyword rules ordered by priority
        keyword_rules = KeywordRule.objects.filter(is_active=True).order_by(
            "-priority", "keyword"
        )

        # Get categories for the form
        categories = Category.objects.filter(parent__isnull=True).order_by("name")

        # Prepare categories data with subcategories for JavaScript
        categories_data = []
        for category in categories:
            subcategories = category.subcategories.all().order_by("name")
            categories_data.append(
                {
                    "id": category.id,
                    "name": category.name,
                    "subcategories": [
                        {"id": sub.id, "name": sub.name} for sub in subcategories
                    ],
                }
            )

        return render(
            request,
            self.template_name,
            {
                "keyword_rules": keyword_rules,
                "categories": categories,
                "categories_json": json.dumps(categories_data),
                "title": "Keyword Categorization Rules",
            },
        )


class AddKeywordRuleView(View):
    """Add a new keyword rule."""

    @method_decorator(trace)
    def post(self, request):
        """Create a new keyword rule."""
        from ..models import KeywordRule, Category

        try:
            keyword = request.POST.get("keyword", "").strip()
            category_id = request.POST.get("category")
            subcategory_id = request.POST.get("subcategory") or None
            priority = int(request.POST.get("priority", 100))

            if not keyword:
                return JsonResponse(
                    {"success": False, "message": "Keyword is required."}
                )

            if not category_id:
                return JsonResponse(
                    {"success": False, "message": "Category is required."}
                )

            # Validate category
            try:
                category = Category.objects.get(id=category_id, parent__isnull=True)
            except Category.DoesNotExist:
                return JsonResponse(
                    {"success": False, "message": "Invalid category selected."}
                )

            # Validate subcategory if provided
            subcategory = None
            if subcategory_id:
                try:
                    subcategory = Category.objects.get(
                        id=subcategory_id, parent=category
                    )
                except Category.DoesNotExist:
                    return JsonResponse(
                        {"success": False, "message": "Invalid subcategory selected."}
                    )

            # Check for duplicate keyword rules
            existing = KeywordRule.objects.filter(
                keyword__iexact=keyword, category=category, subcategory=subcategory
            ).first()

            if existing:
                return JsonResponse(
                    {
                        "success": False,
                        "message": f'A rule for "{keyword}" with this category already exists.',
                    }
                )

            # Create the rule
            rule = KeywordRule.objects.create(
                keyword=keyword,
                category=category,
                subcategory=subcategory,
                priority=priority,
                created_by_user=True,
            )

            logger.info(
                f"Created keyword rule: {keyword} -> {category.name}"
                + (f"/{subcategory.name}" if subcategory else "")
            )

            return JsonResponse(
                {
                    "success": True,
                    "message": f'Keyword rule "{keyword}" created successfully.',
                    "rule_id": rule.id,
                }
            )

        except Exception as e:
            logger.error(f"Error creating keyword rule: {e}")
            return JsonResponse(
                {
                    "success": False,
                    "message": "An error occurred while creating the rule.",
                }
            )


class DeleteKeywordRuleView(View):
    """Delete a keyword rule."""

    @method_decorator(trace)
    def delete(self, request, rule_id):
        """Delete a keyword rule."""
        from ..models import KeywordRule

        try:
            rule = get_object_or_404(KeywordRule, id=rule_id)
            keyword = rule.keyword
            rule.delete()

            logger.info(f"Deleted keyword rule: {keyword}")

            return JsonResponse(
                {
                    "success": True,
                    "message": f'Keyword rule "{keyword}" deleted successfully.',
                }
            )

        except Exception as e:
            logger.error(f"Error deleting keyword rule: {e}")
            return JsonResponse(
                {
                    "success": False,
                    "message": "An error occurred while deleting the rule.",
                }
            )


class LearningPatternsView(View):
    """View and manage all learned AI patterns."""

    template_name = "transactions/learning_patterns.html"

    @method_decorator(trace)
    def get(self, request):
        """Display learning patterns management interface."""
        from ..models import LearnedSubcat, LearnedPayoree, KeywordRule
        from django.db.models import Sum

        # Get all learned patterns
        learned_subcats = LearnedSubcat.objects.select_related(
            "subcategory__parent"
        ).order_by("-count", "key")
        learned_payorees = LearnedPayoree.objects.select_related("payoree").order_by(
            "-count", "key"
        )
        keyword_rules = KeywordRule.objects.filter(is_active=True).order_by(
            "-priority", "keyword"
        )

        # Calculate total confirmations
        total_subcat_confirmations = (
            learned_subcats.aggregate(total=Sum("count"))["total"] or 0
        )
        total_payoree_confirmations = (
            learned_payorees.aggregate(total=Sum("count"))["total"] or 0
        )
        total_confirmations = total_subcat_confirmations + total_payoree_confirmations

        return render(
            request,
            self.template_name,
            {
                "learned_subcats": learned_subcats,
                "learned_payorees": learned_payorees,
                "keyword_rules": keyword_rules,
                "total_confirmations": total_confirmations,
                "title": "AI Learning Patterns",
            },
        )


class ExportLearningDataView(View):
    """Export all learning data as JSON backup."""

    @method_decorator(trace)
    def get(self, request):
        """Export learning data as downloadable JSON file."""
        import json
        from django.http import JsonResponse, HttpResponse
        from ..models import LearnedSubcat, LearnedPayoree, KeywordRule

        try:
            # Collect all learning data
            learning_data = {
                "export_date": timezone.now().isoformat(),
                "version": "1.0",
                "learned_subcats": [],
                "learned_payorees": [],
                "keyword_rules": [],
            }

            # Export learned subcategories
            for learned in LearnedSubcat.objects.select_related("subcategory__parent"):
                learning_data["learned_subcats"].append(
                    {
                        "key": learned.key,
                        "subcategory": learned.subcategory.name,
                        "category": learned.subcategory.parent.name,
                        "count": learned.count,
                        "last_seen": learned.last_seen.isoformat(),
                    }
                )

            # Export learned payorees
            for learned in LearnedPayoree.objects.select_related("payoree"):
                learning_data["learned_payorees"].append(
                    {
                        "key": learned.key,
                        "payoree": learned.payoree.name,
                        "count": learned.count,
                        "last_seen": learned.last_seen.isoformat(),
                    }
                )

            # Export keyword rules
            for rule in KeywordRule.objects.filter(is_active=True).select_related(
                "category", "subcategory"
            ):
                learning_data["keyword_rules"].append(
                    {
                        "keyword": rule.keyword,
                        "category": rule.category.name,
                        "subcategory": (
                            rule.subcategory.name if rule.subcategory else None
                        ),
                        "priority": rule.priority,
                        "created_by_user": rule.created_by_user,
                        "created_at": rule.created_at.isoformat(),
                    }
                )

            # Create response
            response = HttpResponse(
                json.dumps(learning_data, indent=2), content_type="application/json"
            )
            filename = f"budgnudg_learning_backup_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'

            logger.info(
                f"Exported learning data: {len(learning_data['learned_subcats'])} subcats, {len(learning_data['learned_payorees'])} payorees, {len(learning_data['keyword_rules'])} keyword rules"
            )

            return response

        except Exception as e:
            logger.error(f"Error exporting learning data: {e}")
            return JsonResponse(
                {
                    "success": False,
                    "message": "An error occurred while exporting learning data.",
                }
            )


class ImportLearningDataView(View):
    """Import learning data from JSON backup."""

    @method_decorator(trace)
    def post(self, request):
        """Import learning data from uploaded JSON file."""
        import json
        from django.core.files.uploadedfile import UploadedFile
        from ..models import (
            LearnedSubcat,
            LearnedPayoree,
            KeywordRule,
            Category,
            Payoree,
        )
        from datetime import datetime

        try:
            # Get uploaded file
            if "backup_file" not in request.FILES:
                return JsonResponse(
                    {"success": False, "message": "No backup file provided."}
                )

            backup_file = request.FILES["backup_file"]
            merge_data = request.POST.get("merge_data") == "on"

            # Read and parse JSON
            try:
                from transactions.utils import read_uploaded_file

                file_content = read_uploaded_file(backup_file)
                learning_data = json.loads(file_content)
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                return JsonResponse(
                    {"success": False, "message": "Invalid JSON file format."}
                )

            # Validate file structure
            required_keys = ["learned_subcats", "learned_payorees", "keyword_rules"]
            if not all(key in learning_data for key in required_keys):
                return JsonResponse(
                    {"success": False, "message": "Invalid backup file structure."}
                )

            imported_counts = {"subcats": 0, "payorees": 0, "keyword_rules": 0}

            # Clear existing data if not merging
            if not merge_data:
                LearnedSubcat.objects.all().delete()
                LearnedPayoree.objects.all().delete()
                KeywordRule.objects.filter(created_by_user=True).delete()
                logger.info("Cleared existing learning data for full import")

            # Import learned subcategories
            for item in learning_data["learned_subcats"]:
                try:
                    # Find the category and subcategory
                    category = Category.objects.get(
                        name=item["category"], parent__isnull=True
                    )
                    subcategory = Category.objects.get(
                        name=item["subcategory"], parent=category
                    )

                    learned, created = LearnedSubcat.objects.get_or_create(
                        key=item["key"],
                        subcategory=subcategory,
                        defaults={
                            "count": item["count"],
                            "last_seen": datetime.fromisoformat(
                                item["last_seen"]
                            ).date(),
                        },
                    )

                    if not created and merge_data:
                        # Merge counts if already exists
                        learned.count += item["count"]
                        learned.save()

                    imported_counts["subcats"] += 1

                except (Category.DoesNotExist, KeyError) as e:
                    logger.warning(f"Skipped invalid subcategory entry: {item} - {e}")
                    continue

            # Import learned payorees
            for item in learning_data["learned_payorees"]:
                try:
                    # Find or create the payoree
                    payoree, _ = Payoree.objects.get_or_create(name=item["payoree"])

                    learned, created = LearnedPayoree.objects.get_or_create(
                        key=item["key"],
                        payoree=payoree,
                        defaults={
                            "count": item["count"],
                            "last_seen": datetime.fromisoformat(
                                item["last_seen"]
                            ).date(),
                        },
                    )

                    if not created and merge_data:
                        # Merge counts if already exists
                        learned.count += item["count"]
                        learned.save()

                    imported_counts["payorees"] += 1

                except KeyError as e:
                    logger.warning(f"Skipped invalid payoree entry: {item} - {e}")
                    continue

            # Import keyword rules
            for item in learning_data["keyword_rules"]:
                try:
                    # Find the category
                    category = Category.objects.get(
                        name=item["category"], parent__isnull=True
                    )
                    subcategory = None
                    if item.get("subcategory"):
                        subcategory = Category.objects.get(
                            name=item["subcategory"], parent=category
                        )

                    # Check if rule already exists
                    if not KeywordRule.objects.filter(
                        keyword__iexact=item["keyword"],
                        category=category,
                        subcategory=subcategory,
                    ).exists():
                        KeywordRule.objects.create(
                            keyword=item["keyword"],
                            category=category,
                            subcategory=subcategory,
                            priority=item.get("priority", 100),
                            created_by_user=item.get("created_by_user", True),
                        )
                        imported_counts["keyword_rules"] += 1

                except (Category.DoesNotExist, KeyError) as e:
                    logger.warning(f"Skipped invalid keyword rule entry: {item} - {e}")
                    continue

            message = f"Successfully imported {imported_counts['subcats']} subcategory patterns, {imported_counts['payorees']} payoree patterns, and {imported_counts['keyword_rules']} keyword rules."

            logger.info(f"Import completed: {imported_counts}")

            return JsonResponse(
                {
                    "success": True,
                    "message": message,
                    "imported_counts": imported_counts,
                }
            )

        except Exception as e:
            logger.error(f"Error importing learning data: {e}")
            return JsonResponse(
                {
                    "success": False,
                    "message": "An error occurred while importing learning data.",
                }
            )


class DeleteLearnedSubcatView(View):
    """Delete a learned subcategory pattern."""

    @method_decorator(trace)
    def delete(self, request, learned_id):
        """Delete a learned subcategory pattern."""
        from ..models import LearnedSubcat

        try:
            learned = get_object_or_404(LearnedSubcat, id=learned_id)
            pattern_key = learned.key
            learned.delete()

            logger.info(f"Deleted learned subcategory pattern: {pattern_key}")

            return JsonResponse(
                {
                    "success": True,
                    "message": f'Learned pattern "{pattern_key}" deleted successfully.',
                }
            )

        except Exception as e:
            logger.error(f"Error deleting learned subcategory pattern: {e}")
            return JsonResponse(
                {
                    "success": False,
                    "message": "An error occurred while deleting the pattern.",
                }
            )


class DeleteLearnedPayoreeView(View):
    """Delete a learned payoree pattern."""

    @method_decorator(trace)
    def delete(self, request, learned_id):
        """Delete a learned payoree pattern."""
        from ..models import LearnedPayoree

        try:
            learned = get_object_or_404(LearnedPayoree, id=learned_id)
            pattern_key = learned.key
            learned.delete()

            logger.info(f"Deleted learned payoree pattern: {pattern_key}")

            return JsonResponse(
                {
                    "success": True,
                    "message": f'Learned pattern "{pattern_key}" deleted successfully.',
                }
            )

        except Exception as e:
            logger.error(f"Error deleting learned payoree pattern: {e}")
            return JsonResponse(
                {
                    "success": False,
                    "message": "An error occurred while deleting the pattern.",
                }
            )


class ClearAllLearnedSubcatsView(View):
    """Clear all learned subcategory patterns."""

    @method_decorator(trace)
    def post(self, request):
        """Clear all learned subcategory patterns."""
        from ..models import LearnedSubcat

        try:
            count = LearnedSubcat.objects.count()
            LearnedSubcat.objects.all().delete()

            logger.info(f"Cleared {count} learned subcategory patterns")

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Successfully cleared {count} learned subcategory patterns.",
                }
            )

        except Exception as e:
            logger.error(f"Error clearing learned subcategory patterns: {e}")
            return JsonResponse(
                {
                    "success": False,
                    "message": "An error occurred while clearing patterns.",
                }
            )


class ClearAllLearnedPayoreesView(View):
    """Clear all learned payoree patterns."""

    @method_decorator(trace)
    def post(self, request):
        """Clear all learned payoree patterns."""
        from ..models import LearnedPayoree

        try:
            count = LearnedPayoree.objects.count()
            LearnedPayoree.objects.all().delete()

            logger.info(f"Cleared {count} learned payoree patterns")

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Successfully cleared {count} learned payoree patterns.",
                }
            )

        except Exception as e:
            logger.error(f"Error clearing learned payoree patterns: {e}")
            return JsonResponse(
                {
                    "success": False,
                    "message": "An error occurred while clearing patterns.",
                }
            )
