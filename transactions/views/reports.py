from django.views import View
from django.shortcuts import render
from django.utils.decorators import method_decorator
from transactions.utils import trace
# from transactions.selectors import build_time_span_report, build_income_statement

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