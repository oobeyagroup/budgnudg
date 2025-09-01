# transactions/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Transaction, LearnedSubcat, LearnedPayoree
from .utils import trace


@trace
@receiver(post_save, sender=Transaction)
def learn_from_transaction(sender, instance, created, **kwargs):
    if not created:
        return

    # Use payoree name as primary learning key, fallback to description
    if instance.payoree:
        key = instance.payoree.name.upper().strip()
    else:
        key = instance.description.upper().strip() if instance.description else ""
        if not key:
            return

    if instance.subcategory:
        obj, _ = LearnedSubcat.objects.get_or_create(
            key=key, subcategory=instance.subcategory
        )
        obj.count = obj.count + 1
        obj.save()

    if instance.payoree:
        obj, _ = LearnedPayoree.objects.get_or_create(key=key, payoree=instance.payoree)
        obj.count = obj.count + 1
        obj.save()
