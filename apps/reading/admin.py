from django.contrib import admin
from django import forms
from django.db import models
from .models import Reading, ReadingAnswer, ReadingUserAnswer, ReadingMaterial 
    
    
    
class ReadingInline(admin.TabularInline):
    model = Reading
    extra = 1
    show_change_link = True
    
    
@admin.register(ReadingMaterial)
class ReadingMaterialAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "test_material", "get_test_title", "answer_time", "get_readings_count")
    list_editable = ("title", "answer_time")
    list_filter = ("test_material",)
    search_fields = ("title", "test_material__title", "test_material__test__title")

    def answer_time_minutes(self, obj):
        """Display answer_time in minutes"""
        if obj.answer_time:
            minutes, seconds = divmod(obj.answer_time, 60)
            if seconds == 0:
                return f"{minutes} min"
            return f"{minutes} min {seconds} sec"
        return "-"
    answer_time_minutes.short_description = "Answer Time"

    def get_readings_count(self, obj):
        """Count how many readings are attached"""
        return obj.reading_materials.count()
    get_readings_count.short_description = "Readings"

    def get_test_title(self, obj):
        """Show related Test.title from TestMaterial"""
        return obj.test_material.test.title if obj.test_material and obj.test_material.test else "-"
    get_test_title.short_description = "Test Title"


class ReadingAnswerInline(admin.StackedInline):
    model = ReadingAnswer
    extra = 5
    fields = ("question_number", "question", "true_answer")
    can_delete = True
    show_change_link = True
    formfield_overrides = {
        models.TextField: {"widget": forms.Textarea(attrs={"rows": 7, "cols": 80})},
    }


@admin.register(Reading)
class ReadingAdmin(admin.ModelAdmin):
    list_display = ("id", "reading_material", "passage_number", "created_at")
    list_editable = ("reading_material", "passage_number")
    list_filter = ("reading_material", "passage_number", "created_at")
    inlines = [ReadingAnswerInline]
    readonly_fields = ("created_at",)
    list_per_page = 20

    fieldsets = (
        ("General Information", {
            "fields": (
                "reading_material",
                "title",
                "passage_number",
                "content",
                "description",
                "created_at",
            )
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("reading_material")


class ReadingTestTypeListFilter(admin.SimpleListFilter):
    title = "Test Type"
    parameter_name = "test_type"

    def lookups(self, request, model_admin):
        return [
            ("Mock", "Mock"),
            ("Thematic", "Thematic"),
        ]

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            # ✅ To‘g‘ri join yo‘li: reading -> reading_material -> test_material -> test -> test_type
            return queryset.filter(
                reading__reading_material__test_material__test__test_type=value
            )
        return queryset
    
class ReadingListFilter(admin.SimpleListFilter):
    title = "Reading"
    parameter_name = "reading"

    def lookups(self, request, model_admin):
        # Barcha Reading’larni nomi bilan ro‘yxatga qo‘yamiz
        return [(r.id, r.title) for r in Reading.objects.all()]

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(reading_id=value)
        return queryset


@admin.register(ReadingUserAnswer)
class ReadingUserAnswerAdmin(admin.ModelAdmin):
    list_display = ('user', 'reading', 'question_number', 'answer', 'is_true', 'created_at')
    list_filter = (
        ReadingTestTypeListFilter, 
        ReadingListFilter, 
        'user', 
        'reading__reading_material',
        'reading__reading_material__test_material',
        'is_true',
        'created_at'
    )
    search_fields = ('user__username', 'reading__title', 'question_number')

    
    
@admin.register(ReadingAnswer)
class ReadingAnswerAdmin(admin.ModelAdmin):
    list_display = (
        'reading',
        'question_number',
        'question',
        'true_answer',
        'created_at',
    )
    list_filter = (
        'reading',
        'reading__reading_material',
        'reading__reading_material__test_material',
        'question_number',
        'created_at',
    )
    search_fields = (
        'true_answer',
        'question_number',
        'reading__title',
        'reading__reading_material__title',
        'reading__reading_material__test_material__test__title',
    )
    readonly_fields = (
        'reading', 
        'created_at',
    )
    ordering = (
        'reading',
        'question_number',
    )
    list_per_page = 20

