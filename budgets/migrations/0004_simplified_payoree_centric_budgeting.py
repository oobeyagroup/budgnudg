# Generated manually for clean slate payoree-centric budgeting refactor

from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('transactions', '0001_initial'),  # Ensure payoree table exists
        ('budgets', '0003_budgetplan_budgetallocation_delete_budget_and_more'),
    ]

    operations = [
        # Drop existing BudgetAllocation table completely (SQLite compatible)
        migrations.RunSQL(
            "DROP TABLE IF EXISTS budgets_budgetallocation;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        
        # Drop existing indexes that reference the old table (SQLite compatible)
        migrations.RunSQL(
            "DROP INDEX IF EXISTS budgets_bud_budget__0e76b5_idx;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            "DROP INDEX IF EXISTS budgets_bud_categor_54365f_idx;", 
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            "DROP INDEX IF EXISTS budgets_bud_subcate_e85c85_idx;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            "DROP INDEX IF EXISTS budgets_bud_payoree_1d5741_idx;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        
        # Create the simplified BudgetAllocation table
        migrations.CreateModel(
            name='BudgetAllocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, help_text='Allocation amount (positive for income, negative for expenses)', max_digits=12)),
                ('is_ai_suggested', models.BooleanField(default=False, help_text='True if this allocation was auto-populated by AI')),
                ('baseline_amount', models.DecimalField(blank=True, decimal_places=2, help_text='Historical baseline used for AI suggestion', max_digits=12, null=True)),
                ('user_note', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('budget_plan', models.ForeignKey(help_text='Budget plan this allocation belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='allocations', to='budgets.budgetplan')),
                ('payoree', models.ForeignKey(help_text='Payoree for this budget allocation', on_delete=django.db.models.deletion.CASCADE, to='transactions.payoree')),
                ('recurring_series', models.ForeignKey(blank=True, help_text='Connected recurring transaction series', null=True, on_delete=django.db.models.deletion.SET_NULL, to='transactions.recurringseries')),
            ],
            options={
                'ordering': ['budget_plan', 'payoree__name'],
            },
        ),
        
        # Add unique constraint
        migrations.AddConstraint(
            model_name='budgetallocation',
            constraint=models.UniqueConstraint(fields=('budget_plan', 'payoree'), name='unique_budget_payoree'),
        ),
        
        # Add indexes for performance
        migrations.AddIndex(
            model_name='budgetallocation',
            index=models.Index(fields=['budget_plan'], name='budgets_bud_budget__0e76b5_idx'),
        ),
        migrations.AddIndex(
            model_name='budgetallocation',
            index=models.Index(fields=['payoree'], name='budgets_bud_payoree_1d5741_idx'),
        ),
    ]