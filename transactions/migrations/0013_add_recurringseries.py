# Generated migration for RecurringSeries (minimal hand-authored)
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("transactions", "0012_rename_transaction_date_c0566d_idx_transaction_date_7d5da2_idx_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="RecurringSeries",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ("merchant_key", models.CharField(max_length=200, db_index=True)),
                ("amount_cents", models.IntegerField()),
                ("amount_tolerance_cents", models.IntegerField(default=100)),
                ("interval", models.CharField(choices=[('weekly', 'Weekly'), ('biweekly', 'Biweekly'), ('monthly', 'Monthly'), ('quarterly', 'Quarterly'), ('yearly', 'Yearly')], max_length=20)),
                ("confidence", models.FloatField(default=0.0)),
                ("first_seen", models.DateField(null=True, blank=True)),
                ("last_seen", models.DateField(null=True, blank=True)),
                ("next_due", models.DateField(null=True, blank=True)),
                ("active", models.BooleanField(default=True)),
                ("notes", models.TextField(blank=True, default="")),
                ("payoree", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='transactions.Payoree')),
                ("seed_transaction", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='seeded_series', to='transactions.Transaction')),
            ],
            options={
                'indexes': [models.Index(fields=['merchant_key', 'amount_cents'], name='transactions_recurring_merchant_amount_idx'), models.Index(fields=['next_due'], name='transactions_recurring_next_due_idx'), models.Index(fields=['active'], name='transactions_recurring_active_idx')],
            },
        ),
    ]
