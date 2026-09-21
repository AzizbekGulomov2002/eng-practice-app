from django.apps import AppConfig


class SpeakingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.speaking'
    
    def ready(self):
        """Signal larni register qilish"""
        import apps.speaking.signals  # noqa