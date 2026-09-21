import mimetypes
from django.contrib import admin
from django.utils.html import format_html
from apps.speaking.models import SpeakingMaterial, Speaking, SpeakingAnswer, SpeakingUserAnswer


class SpeakingAnswerInline(admin.TabularInline):
    model = SpeakingAnswer
    extra = 0
    fields = ("question_number", "question")
    show_change_link = True


class SpeakingInline(admin.TabularInline):
    model = Speaking
    extra = 0
    fields = ("speaking_part", "comment")
    show_change_link = True


@admin.register(SpeakingMaterial)
class SpeakingMaterialAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "test_material", "speaking_list")
    search_fields = ("title", "test_material__title")
    # inlines = [SpeakingInline]

    def speaking_list(self, obj):
        speakings = obj.speaking_sections.all().order_by("speaking_part")
        if not speakings.exists():
            return "—"
        return ", ".join([f"Part {s.speaking_part}" for s in speakings])

    speaking_list.short_description = "Speakings"


@admin.register(Speaking)
class SpeakingAdmin(admin.ModelAdmin):
    list_display = ("id", "speaking_material", "speaking_part","prep_time", "answer_time", "comment")
    list_editable = ("speaking_material", "speaking_part", "prep_time", "answer_time")
    list_filter = ("speaking_material", "speaking_part")
    search_fields = ("speaking_material__title", "comment")
    inlines = [SpeakingAnswerInline]


@admin.register(SpeakingAnswer)
class SpeakingAnswerAdmin(admin.ModelAdmin):
    list_display = ("id", "speaking", "question_number", "question")
    list_filter = ("speaking",)
    search_fields = ("question",)
    
@admin.register(SpeakingUserAnswer)
class SpeakingUserAnswerAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "speaking", "audio_player", "score", "created_at")
    search_fields = ("user__username", "speaking__comment")
    ordering = ("-id",)

    def audio_player(self, obj):
        if obj.record:
            try:
                # Faylning MIME turini aniqlaymiz
                file_name_lower = str(obj.record.name).lower()
                file_name_display = file_name_lower.split('/')[-1] if '/' in file_name_lower else file_name_lower
                
                # WebM fayllar uchun to'g'ri MIME type ni o'rnatish
                if file_name_lower.endswith('.webm'):
                    mime_type = "audio/webm"
                elif file_name_lower.endswith('.mp3'):
                    mime_type = "audio/mpeg"
                elif file_name_lower.endswith('.wav'):
                    mime_type = "audio/wav"
                elif file_name_lower.endswith('.ogg'):
                    mime_type = "audio/ogg"
                elif file_name_lower.endswith('.m4a'):
                    mime_type = "audio/mp4"
                else:
                    mime_type, _ = mimetypes.guess_type(obj.record.url)
                    if not mime_type:
                        mime_type = "audio/mpeg"
                
                # URL ni to'g'ri formatlash (format_html avtomatik escape qiladi)
                audio_url = obj.record.url
                
                # HTML5 audio element - to'liq funksiyalar bilan
                # preload="none" - broken pipe xatosini oldini olish uchun
                # controls - barcha boshqaruv elementlarini ko'rsatish
                return format_html(
                    '<div class="speaking-audio-player-wrapper">'
                    '<div style="display: flex; align-items: center; gap: 8px;">'
                    '<audio controls preload="none" style="flex: 1; height: 40px;">'
                    '<source src="{}" type="{}">'
                    'Your browser does not support the audio element.'
                    '</audio>'
                    '<a href="{}" download="{}" class="audio-download-btn" title="Yuklab olish (Download)">'
                    '<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">'
                    '<path d="M19 12v7H5v-7H3v7c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2v-7h-2zm-6 .67l2.59-2.58L17 11.5l-5 5-5-5 1.41-1.41L11 12.67V3h2z"/>'
                    '</svg>'
                    '</a>'
                    '</div>'
                    '</div>',
                    audio_url,
                    mime_type,
                    audio_url,
                    file_name_display
                )
            except Exception as e:
                # Xatolik bo'lsa, oddiy link ko'rsatamiz
                return format_html(
                    '<a href="{}" target="_blank" style="color: #667eea;">Audio fayl</a>',
                    obj.record.url if obj.record else '#'
                )
        return format_html('<span style="color: #999;">No Record</span>')

    audio_player.short_description = "Audio"
    
    class Media:
        """Custom CSS faylni admin ga qo'shish"""
        css = {
            'all': ('assets/css/speaking-admin-audio.css',)
        }