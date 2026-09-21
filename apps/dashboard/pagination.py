from urllib.parse import urlencode
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from rest_framework.views import APIView
from django.db.models import Q

class BasePaginationView(APIView):
    page_size = 10
    search_fields = [] 
    
    def paginate_queryset(self, queryset, request):
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', self.page_size))
        if page_size > 100:
            page_size = 100
        if page_size < 1:
            page_size = self.page_size
        paginator = Paginator(queryset, page_size)

        try:
            page_obj = paginator.page(page)
        except PageNotAnInteger:
            page = 1
            page_obj = paginator.page(page)
        except EmptyPage:
            page = paginator.num_pages if paginator.num_pages > 0 else 1
            page_obj = paginator.page(page) if paginator.num_pages > 0 else paginator.page(1)

        base_url = request.build_absolute_uri(request.path)
        query_params = request.GET.copy()

        def build_url(page_number):
            query_params["page"] = page_number
            query_params["page_size"] = page_size
            return f"{base_url}?{urlencode(query_params)}"

        next_url = build_url(page + 1) if page_obj.has_next() else None
        prev_url = build_url(page - 1) if page_obj.has_previous() else None

        return {
            "count": paginator.count,
            "total_pages": paginator.num_pages,
            "current_page": page,
            "page_size": page_size,
            "next": next_url,
            "previous": prev_url,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
            "results": list(page_obj)
        }

    def filter_queryset(self, queryset, request):
        """Universal search by search_fields"""
        search = request.GET.get("search")
        if search and self.search_fields:
            query = Q()
            for field in self.search_fields:
                query |= Q(**{f"{field}__icontains": search})
            queryset = queryset.filter(query)
        return queryset
