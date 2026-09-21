import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ListeningUserAnswer

logger = logging.getLogger(__name__)

@receiver(post_save, sender=ListeningUserAnswer)
def log_listening_user_answer(sender, instance, created, **kwargs):
    if instance.user.role == "Student":
        action = "created" if created else "updated"
        logger.info(
            f"[ListeningUserAnswer] Student {instance.user} {action} answer "
            f"Q{instance.question_number} -> {instance.answer} | Correct: {instance.is_true}"
        )

# @receiver(post_save, sender=WritingUserAnswer)
# def log_writing_user_answer(sender, instance, created, **kwargs):
#     if instance.user.role == "Student":
#         action = "created" if created else "updated"
#         logger.info(
#             f"[WritingUserAnswer] Student {instance.user} {action} answer "
#             f"Q{instance.question_number} -> {instance.answer} | Score: {instance.score}"
#         )
