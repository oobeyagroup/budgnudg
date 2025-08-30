from django.views import View
from django.shortcuts import render
from django.utils.decorators import method_decorator
from transactions.utils import trace

# from transactions.selectors import build_time_span_report, build_income_statement
from transactions.selectors import build_upcoming_forecast


class UpcomingReportView(View):
    template_name = "transactions/upcoming_report.html"

    @method_decorator(trace)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @method_decorator(trace)
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
        for idx, d in enumerate(days):
            rows.append(
                {
                    "date": d,
                    "income": daily_income[idx] if idx < len(daily_income) else 0,
                    "expense": daily_expense[idx] if idx < len(daily_expense) else 0,
                    "net": daily_net[idx] if idx < len(daily_net) else 0,
                    "transactions": daily_transactions.get(d, []),
                }
            )

        ctx = {"rows": rows, "weeks": weeks, "totals": forecast.get("totals", {})}
        return render(request, self.template_name, ctx)


class ReportAccountTimeSpanView(View):
    template_name = "transactions/report_account_time_span.html"

    @method_decorator(trace)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @method_decorator(trace)
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

    @method_decorator(trace)
    def get(self, request):
        ctx = {
            # "report": build_income_statement()
        }
        return render(request, self.template_name, ctx)
