"""
Speaking app signals
WebM fayllarni MP3 ga avtomatik convert qilish
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from apps.speaking.models import SpeakingUserAnswer
from apps.speaking.utils import convert_audio_to_mp3_async


# Oldingi record qiymatini saqlash uchun (temporary storage)
_previous_record = {}


@receiver(pre_save, sender=SpeakingUserAnswer)
def store_previous_record(sender, instance, **kwargs):
    """
    Save dan oldin eski record qiymatini saqlash
    """
    if instance.pk:
        try:
            old_instance = SpeakingUserAnswer.objects.get(pk=instance.pk)
            _previous_record[instance.pk] = old_instance.record.name if old_instance.record else None
        except SpeakingUserAnswer.DoesNotExist:
            _previous_record[instance.pk] = None


@receiver(post_save, sender=SpeakingUserAnswer)
def convert_audio_to_mp3_on_save(sender, instance, created, **kwargs):
    """
    SpeakingUserAnswer yaratilganda yoki record o'zgarganda,
    agar record MP3 bo'lmagan audio formatida bo'lsa, uni MP3 ga convert qilish
    Faqat admin panel yoki boshqa joydan yuklanganda ishlaydi
    (API dan yuklanganda views.py da sinxron convert qilinadi)
    """
    # Faqat record mavjud bo'lsa
    if not instance.record:
        # Oldingi record ni tozalash
        if instance.pk in _previous_record:
            del _previous_record[instance.pk]
        return
    
    file_name = str(instance.record.name).lower() if instance.record.name else ""
    
    # MP3 fayllarni o'tkazib yuborish
    if file_name.endswith('.mp3'):
        # Oldingi record ni tozalash
        if instance.pk in _previous_record:
            del _previous_record[instance.pk]
        return
    
    # Yangi yaratilgan yoki record o'zgargan bo'lsa
    should_convert = False
    
    if created:
        # Yangi yaratilgan - lekin API dan yuklanganda views.py da convert qilinadi
        # Shuning uchun bu yerda faqat admin panel yoki boshqa joydan yuklanganda ishlaydi
        # API dan yuklanganda signal ishlaydi, lekin views.py da allaqachon convert qilingan bo'lishi mumkin
        # Shuning uchun tekshiramiz - agar fayl hali WebM bo'lsa, convert qilamiz
        should_convert = True
    elif instance.pk:
        # Record o'zgarganmi tekshirish
        previous_record = _previous_record.get(instance.pk, None)
        current_record = instance.record.name if instance.record else None
        if previous_record != current_record:
            should_convert = True
    
    if should_convert:
        # Background thread da convert qilish (admin panel uchun)
        convert_audio_to_mp3_async(instance)
    
    # Oldingi record ni tozalash
    if instance.pk in _previous_record:
        del _previous_record[instance.pk]

