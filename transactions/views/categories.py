from django.views.generic import ListView
from django.utils.decorators import method_decorator
from transactions.models import Category
from transactions.utils import trace

class CategoriesListView(ListView):
    template_name = "transactions/categories_list.html"
    context_object_name = "categories"
    paginate_by = 100

    @method_decorator(trace)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @method_decorator(trace)
    def get_queryset(self):
        return Category.objects.select_related("parent").order_by("parent__name", "name")

    @method_decorator(trace)
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        return ctx