from venv import logger
from django.views import View
from django.shortcuts import render
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from transactions.utils import trace
import datetime as dt

# from transactions.selectors import build_time_span_report, build_income_statement
from transactions.selectors import build_upcoming_forecast
from transactions.models import RecurringSeries

from datetime import date
from django.views.generic import TemplateView
from django.db.models import Q
from transactions.reporting.pivot import MonthlyPivot, MonthlyPivotSpec


class UpcomingReportView(View):
    template_name = "transactions/upcoming_report.html"

    @method_decorator(trace)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        weeks = int(request.GET.get("weeks", 4))
        forecast = build_upcoming_forecast(weeks=weeks)

        # build rows per-day
        rows = []
        days = forecast.get("days", [])
        daily_income = forecast.get("daily_income", [])
        daily_expense = forecast.get("daily_expense", [])
        daily_net = forecast.get("daily_net", [])
        daily_transactions = forecast.get("daily_transactions", {})
        # group transactions per week and compute per-week subtotal of transaction values
        weeks_map: dict[dt.date, dict] = {}
        for idx, d in enumerate(days):
            txs = daily_transactions.get(d, [])
            # skip days with no transactions as requested
            if not txs:
                continue
            logger.debug(f"Processing transactions for {d}:")
            logger.debug(f"{txs}")
            # sum transaction amounts for the day
            tx_sum = sum(float(t.get("amount", 0)) for t in txs)
            # determine week start for this day
            ws = d - dt.timedelta(days=d.weekday())
            if ws not in weeks_map:
                weeks_map[ws] = {"rows": [], "week_total": 0.0}
            weeks_map[ws]["week_total"] += tx_sum
            weeks_map[ws]["rows"].append(
                {
                    "date": d,
                    "income": daily_income[idx] if idx < len(daily_income) else 0,
                    "expense": daily_expense[idx] if idx < len(daily_expense) else 0,
                    "net": daily_net[idx] if idx < len(daily_net) else 0,
                    "transactions": txs,
                    "transactions_total": tx_sum,
                }
            )

        # convert weeks_map to ordered list by week start
        weeks_list = [
            {"week_start": k, "rows": v["rows"], "week_total": v["week_total"]}
            for k, v in sorted(weeks_map.items())
        ]
        ctx = {
            "weeks": weeks_list,
            "weeks_count": weeks,
            "totals": forecast.get("totals", {}),
        }
        return render(request, self.template_name, ctx)

    @method_decorator(csrf_exempt)
    @method_decorator(trace)
    def post(self, request):
        """Handle POST request to disable a recurring series."""
        try:
            series_id = request.POST.get("series_id")
            if not series_id:
                return JsonResponse(
                    {"success": False, "error": "Series ID is required"}, status=400
                )

            # Get the recurring series
            series = RecurringSeries.objects.get(id=series_id)

            # Mark as manually disabled
            series.manually_disabled = True
            series.save()

            return JsonResponse(
                {
                    "success": True,
                    "message": f'Series "{str(series)}" has been disabled',
                }
            )

        except RecurringSeries.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "Recurring series not found"}, status=404
            )
        except Exception as e:
            logger.error(f"Error disabling recurring series: {e}")
            return JsonResponse(
                {
                    "success": False,
                    "error": "An error occurred while disabling the series",
                },
                status=500,
            )


class ReportAccountTimeSpanView(View):
    template_name = "transactions/report_account_time_span.html"

    @method_decorator(trace)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        ctx = {
            # "report": build_time_span_report()
        }
        return render(request, self.template_name, ctx)


class ReportIncomeStatementView(View):
    template_name = "transactions/report_income_statement.html"

    @method_decorator(trace)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        ctx = {
            # "report": build_income_statement()
        }
        return render(request, self.template_name, ctx)


class BudgetMonthlyReport2(TemplateView):
    template_name = "transactions/report_budget.html"

    @method_decorator(trace)
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # Example: show expense categories only (amount < 0), current year
        spec = MonthlyPivotSpec(
            dimension_expr="subcategory__parent__name",  # top-level category name
            metric_expr="amount",
            filters=Q(amount__lt=0),
            start=date(date.today().year, 1, 1),
        )
        months, rows = MonthlyPivot(spec).run()

        ctx.update({
            "months": months,
            "rows": rows,
            "heading": "Category",
            "title": "Budget (Monthly, by Category)",
        })
        return ctx
    
    