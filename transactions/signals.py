# transactions/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Transaction, LearnedSubcat, LearnedPayoree
from .categorization import extract_merchant_from_description
from .utils import trace

@trace
@receiver(post_save, sender=Transaction)
def learn_from_transaction(sender, instance, created, **kwargs):
    if not created:
        return
    key = extract_merchant_from_description(instance.description or "")
    if not key:
        return

    if instance.subcategory:
        obj, _ = LearnedSubcat.objects.get_or_create(key=key, subcategory=instance.subcategory)
        obj.count = obj.count + 1
        obj.save()

    if instance.payoree:
        obj, _ = LearnedPayoree.objects.get_or_create(key=key, payoree=instance.payoree)
        obj.count = obj.count + 1
        obj.save()
