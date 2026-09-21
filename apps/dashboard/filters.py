from apps.app.models import Users
from django.db.models import Q
import django_filters


class StudentResultFilter(django_filters.FilterSet):
    group = django_filters.CharFilter(field_name='student_group__name', lookup_expr='icontains')
    test_number = django_filters.CharFilter(method='filter_by_test_number')
    test_type = django_filters.CharFilter(method='filter_by_test_type')
    date_from = django_filters.DateFilter(method='filter_date_from')
    date_to = django_filters.DateFilter(method='filter_date_to')
    has_reading = django_filters.BooleanFilter(method='filter_has_reading')
    has_listening = django_filters.BooleanFilter(method='filter_has_listening')
    has_writing = django_filters.BooleanFilter(method='filter_has_writing')
    has_speaking = django_filters.BooleanFilter(method='filter_has_speaking')
    
    class Meta:
        model = Users
        fields = ['group', 'test_number', 'test_type', 'date_from', 'date_to', 'has_reading', 'has_listening', 'has_writing', 'has_speaking']
    
    def filter_by_test_number(self, queryset, name, value):
        return queryset.filter(
            Q(reading_user_answers__reading__reading_material__test_material__test__test_number__icontains=value) |
            Q(listening_user_answers__listening__listening_material__test_material__test__test_number__icontains=value) |
            Q(writing_user_answers__writing__writing_material__test_material__test__test_number__icontains=value) |
            Q(speaking_user_answers__speaking__speaking_material__test_material__test__test_number__icontains=value)
        ).distinct()
    
    def filter_by_test_type(self, queryset, name, value):
        return queryset.filter(
            Q(reading_user_answers__reading__reading_material__test_material__test__test_type__icontains=value) |
            Q(listening_user_answers__listening__listening_material__test_material__test__test_type__icontains=value) |
            Q(writing_user_answers__writing__writing_material__test_material__test__test_type__icontains=value) |
            Q(speaking_user_answers__speaking__speaking_material__test_material__test__test_type__icontains=value)
        ).distinct()
    
    def filter_date_from(self, queryset, name, value):
        return queryset.filter(
            Q(reading_user_answers__created_at__gte=value) |
            Q(listening_user_answers__created_at__gte=value) |
            Q(writing_user_answers__created_at__gte=value) |
            Q(speaking_user_answers__created_at__gte=value)
        ).distinct()
    
    def filter_date_to(self, queryset, name, value):
        return queryset.filter(
            Q(reading_user_answers__created_at__lte=value) |
            Q(listening_user_answers__created_at__lte=value) |
            Q(writing_user_answers__created_at__lte=value) |
            Q(speaking_user_answers__created_at__lte=value)
        ).distinct()
    
    def filter_has_reading(self, queryset, name, value):
        if value:
            return queryset.filter(reading_user_answers__isnull=False).distinct()
        return queryset.exclude(reading_user_answers__isnull=False).distinct()
    
    def filter_has_listening(self, queryset, name, value):
        if value:
            return queryset.filter(listening_user_answers__isnull=False).distinct()
        return queryset.exclude(listening_user_answers__isnull=False).distinct()
    
    def filter_has_writing(self, queryset, name, value):
        if value:
            return queryset.filter(writing_user_answers__isnull=False).distinct()
        return queryset.exclude(writing_user_answers__isnull=False).distinct()
    
    def filter_has_speaking(self, queryset, name, value):
        if value:
            return queryset.filter(speaking_user_answers__isnull=False).distinct()
        return queryset.exclude(speaking_user_answers__isnull=False).distinct()



