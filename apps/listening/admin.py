from django.contrib import admin
from django.utils.html import format_html
from django import forms
from django.db import models
from .models import ListeningMaterial, Listening, ListeningAnswer, ListeningUserAnswer


@admin.register(ListeningMaterial)
class ListeningMaterialAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "test_material", "answer_time", "answer_time_minutes", "get_listenings_count")
    list_editable = ("title", "answer_time")
    list_display_links = ("id", "test_material")
    list_filter = ("test_material",)
    search_fields = ("title", "test_material__title")

    @admin.display(ordering="answer_time", description="Answer Time (minutes)")
    def answer_time_minutes(self, obj):
        """Display answer_time in minutes"""
        if obj.answer_time:
            minutes, seconds = divmod(obj.answer_time, 60)
            if seconds == 0:
                return f"{minutes} min"
            return f"{minutes} min {seconds} sec"
        return "-"
    
    def get_listenings_count(self, obj):
        """Count how many listenings are attached"""
        return obj.listening_sections.count()
    get_listenings_count.short_description = "Listenings"


class ListeningAnswerInline(admin.StackedInline):
    model = ListeningAnswer
    extra = 5
    fields = ("question_number", "question", "true_answer")
    can_delete = True
    show_change_link = True
    formfield_overrides = {
        models.TextField: {"widget": forms.Textarea(attrs={"rows": 7, "cols": 80})},
    }


class ListeningAdminForm(forms.ModelForm):
    """Custom form for Listening admin with audio upload in list view"""
    class Meta:
        model = Listening
        exclude = ("questions", "questions_raw")
        widgets = {
            "audio": forms.FileInput(attrs={"style": "width: 200px;"}),
        }


@admin.register(Listening)
class ListeningAdmin(admin.ModelAdmin):
    form = ListeningAdminForm
    list_display = (
        'id',
        'listening_material',
        'answer_time_seconds',
        'listening_section',
        'title',
        'audio',
        'audio_player',
        'is_script',
    )
    list_editable = ('listening_material', 'listening_section', 'audio', 'is_script')
    list_filter = ('listening_material', 'listening_section', 'is_script')
    search_fields = ('listening_material__title', 'title', 'description')
    inlines = [ListeningAnswerInline]
    list_per_page = 20
    
    def audio_player(self, obj):
        """Display audio player in list view"""
        if obj.audio:
            return format_html(
                '<audio controls style="width: 250px; height: 30px;">'
                '<source src="{}" type="audio/mpeg">'
                'Your browser does not support the audio element.'
                '</audio>',
                obj.audio.url
            )
        return "-"
    audio_player.short_description = "Audio Player"

    fieldsets = (
        ('General Information', {
            'fields': (
                'listening_material',
                'title',
                'audio',
                'listening_section',
                'audioscript',
                'description',
                'is_script'
            )
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('listening_material')

    @admin.display(ordering='listening_material__answer_time', description='Answer Time (seconds)')
    def answer_time_seconds(self, obj):
        """Show related ListeningMaterial.answer_time in seconds."""
        if obj.listening_material and obj.listening_material.answer_time is not None:
            return obj.listening_material.answer_time
        return "-"


@admin.register(ListeningAnswer)
class ListeningAnswerAdmin(admin.ModelAdmin):
    list_display = (
        'listening',
        'question_number',
        'question',
        'true_answer',
        'created_at',
    )
    list_filter = (
        'listening',
        'listening__listening_material',
        'listening__listening_material__test_material',
        'question_number',
        'created_at',
    )
    search_fields = (
        'true_answer',
        'question_number',
        'listening__title',
        'listening__listening_material__title',
        'listening__listening_material__test_material__test__title',
    )
    readonly_fields = (
        'listening',
        'created_at',
    )
    ordering = ('listening', 'question_number')
    list_per_page = 20


class TestTypeListFilter(admin.SimpleListFilter):
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
            return queryset.filter(
                listening__listening_material__test_material__test__test_type=value
            )
        return queryset


class ListeningListFilter(admin.SimpleListFilter):
    title = "Listening"
    parameter_name = "listening"

    def lookups(self, request, model_admin):
        # Barcha Listening'larni nomi bilan ro'yxatga qo'yamiz
        return [(l.id, l.title or f"Part {l.listening_section}") for l in Listening.objects.all()]

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(listening_id=value)
        return queryset


@admin.register(ListeningUserAnswer)
class ListeningUserAnswerAdmin(admin.ModelAdmin):
    list_display = ('user', 'listening', 'question_number', 'answer', 'is_true', 'created_at')
    list_filter = (
        TestTypeListFilter, 
        ListeningListFilter, 
        'user', 
        'listening__listening_material',
        'listening__listening_material__test_material',
        'is_true',
        'created_at'
    )
    search_fields = ('user__username', 'listening__title', 'question_number')




