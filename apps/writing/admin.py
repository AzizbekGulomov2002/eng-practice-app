from django.contrib import admin
from .models import Writing, WritingMaterial, WritingAnswer, WritingUserAnswer
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import WritingUserAnswer, Writing

class WritingInline(admin.TabularInline):
    """WritingMaterial ichida Writing inline ko‘rsatish"""
    model = Writing
    extra = 0
    fields = (
        "writing_task",
        "description",
        "created_at",
    )
    readonly_fields = ("created_at",)
    show_change_link = True


class WritingAnswerInline(admin.StackedInline): 
    """Writing ichida WritingAnswer inline ko‘rsatish"""
    model = WritingAnswer
    extra = 1
    fields = ("question_number", "question")
    show_change_link = True


@admin.register(WritingMaterial)
class WritingMaterialAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "test_material", "answer_time")
    list_editable = ("title", "answer_time")
    list_filter = ("test_material",)
    search_fields = ("title", "test_material__title")
    list_per_page = 20
    # inlines = [WritingInline]

    def answer_time_minutes(self, obj):
        if obj.answer_time:
            minutes, seconds = divmod(obj.answer_time, 60)
            if seconds == 0:
                return f"{minutes} min"
            return f"{minutes} min {seconds} sec"
        return "-"
    answer_time_minutes.short_description = "Answer Time"


@admin.register(Writing)
class WritingAdmin(admin.ModelAdmin):
    """Writing admin paneli"""
    list_display = ("id", "writing_task", "writing_material",  "created_at")
    list_editable = ("writing_material", "writing_task")
    list_filter = ("writing_task", "writing_material__test_material")
    search_fields = ("writing_material__title", "description")
    readonly_fields = ("created_at",)
    list_per_page = 20
    inlines = [WritingAnswerInline]


@admin.register(WritingAnswer)
class WritingAnswerAdmin(admin.ModelAdmin):
    """WritingAnswer admin paneli"""
    list_display = ("id", "writing", "writing_material", "question_number", "short_question")
    list_filter = ("writing", "writing__writing_material")
    search_fields = ("question", "writing__description", "writing__writing_material__title")

    @admin.display(description="Writing Material")
    def writing_material(self, obj):
        return obj.writing.writing_material.title if obj.writing.writing_material else "-"

    @admin.display(description="Question")
    def short_question(self, obj):
        if obj.question and len(obj.question) > 80:
            return f"{obj.question[:80]}..."
        return obj.question



class TestTypeFilter(admin.SimpleListFilter):
    title = _('Test Type')  # Admin panelda ko‘rinadigan nomi
    parameter_name = 'test_type'  # URL query param nomi (?test_type=Mock)

    def lookups(self, request, model_admin):
        # Barcha mavjud test_type larni qaytarish
        test_types = (
            Writing.objects
            .select_related('writing_material__test_material__test')
            .values_list('writing_material__test_material__test__test_type', flat=True)
            .distinct()
        )
        return [(t, t) for t in test_types if t]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(
                writing__writing_material__test_material__test__test_type=self.value()
            )
        return queryset


@admin.register(WritingUserAnswer)
class WritingUserAnswerAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "writing", "writing_material", "question_number", "short_answer", "feedback", "score", "word_count", "created_at")
    list_filter = (
        "writing",
        "writing__writing_material",
        "writing__writing_task",
        "user",
        TestTypeFilter,
        "created_at",
    )
    search_fields = ("user__username", "writing__description", "writing__writing_material__title")
    ordering = ("-id",)

    @admin.display(description="Writing Material")
    def writing_material(self, obj):
        return obj.writing.writing_material.title if obj.writing.writing_material else "-"

    @admin.display(description="Answer")
    def short_answer(self, obj):
        if obj.answer and len(obj.answer) > 100:
            return f"{obj.answer[:100]}..."
        return obj.answer

    @admin.display(description="Word Count")
    def word_count(self, obj):
        return obj.word_count


