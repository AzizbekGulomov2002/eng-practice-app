from django.db import models
from ckeditor.fields import RichTextField
from apps.app.models import TestMaterial, Users

class SpeakingMaterial(models.Model):
    test_material = models.ForeignKey("app.TestMaterial", on_delete=models.CASCADE, related_name="speaking_materials")
    title = models.CharField(max_length=200, null=True, blank=True)
    
    def __str__(self):
        return str(self.title)

class Speaking(models.Model):
    speaking_material = models.ForeignKey(
        SpeakingMaterial, on_delete=models.CASCADE, related_name='speaking_sections'
    )
    prep_time = models.PositiveIntegerField(default=5,verbose_name="Prep Time (seconds)")
    answer_time = models.PositiveIntegerField(default=20,verbose_name="Answer Time (seconds)")
    SPEAKING_PART_CHOICES = (
        (1, 'Part 1'),
        (2, 'Part 2'),
        (3, 'Part 3'),
    )
    
    speaking_part = models.IntegerField(choices=SPEAKING_PART_CHOICES)
    comment = models.TextField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = 'Speakings'
        verbose_name_plural = 'Speakings'
        unique_together = ('speaking_material', 'speaking_part') 

    def __str__(self):
        return f"Part {self.speaking_part} ({self.get_speaking_part_display()})"
     
class SpeakingAnswer(models.Model):
    speaking = models.ForeignKey(Speaking, on_delete=models.CASCADE, related_name='speaking_answer')
    question_number = models.PositiveIntegerField()
    question = RichTextField(verbose_name="Question")
    class Meta:
        verbose_name = 'Speaking Question'
        verbose_name_plural = 'Speaking Questions'

    def __str__(self):
        return f"Q{self.question_number}: {self.question[:30]}"

class SpeakingUserAnswer(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='speaking_user_answers')
    speaking = models.ForeignKey(SpeakingMaterial, on_delete=models.CASCADE, related_name='answers')
    question_number = models.PositiveIntegerField(default=1) 
    record = models.FileField(upload_to='speaking_records/')
    
    feedback = models.TextField(null=True, blank=True)
    score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Speaking Answer'
        verbose_name_plural = 'Speaking Answers'
        unique_together = ('user', 'speaking', 'question_number') 
        ordering = ['-created_at']

    def __str__(self):
        title = self.speaking.title if self.speaking.title else "Speaking Test"
        return f"Answer by {self.user.username} for {title} - Q{self.question_number}"



    
    
    
    