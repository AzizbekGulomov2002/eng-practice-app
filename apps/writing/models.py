import re
from django.db import models
from apps.app.models import TestMaterial, Users
from ckeditor.fields import RichTextField


class WritingMaterial(models.Model):
    test_material = models.ForeignKey("app.TestMaterial", on_delete=models.CASCADE, related_name="writing_materials")
    title = models.CharField(max_length=200, null=True, blank=True)
    answer_time = models.PositiveIntegerField(default=3600, verbose_name="Answer Time (seconds)", help_text="Answer time (seconds)")
    
    def __str__(self):
        if self.title:  
            return self.title  
        elif self.test_material:  
            return str(self.test_material)  
        return "Unnamed Writing Material"
    
class Writing(models.Model):
    writing_material = models.ForeignKey(WritingMaterial, on_delete=models.CASCADE, related_name='writing_materials')
    WRITING_TASK_CHOICES = (
        (1, 'Part 1'),
        (2, 'Part 2'),
    )
    writing_task = models.IntegerField(choices=WRITING_TASK_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    description = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = 'Writings'
        verbose_name_plural = 'Writings'

    def __str__(self):
        return f"Writing Part {self.writing_task}"


    @property
    def test_material(self):
        return self.writing_material.test_material

class WritingAnswer(models.Model):
    writing = models.ForeignKey(Writing, on_delete=models.CASCADE, related_name='writing_answers')
    question_number = models.PositiveBigIntegerField(default=1)
    question = RichTextField()

    class Meta:
        verbose_name = 'Writing Question'
        verbose_name_plural = 'Writing Questions'

    def __str__(self):
        return f"Answer by"

class WritingUserAnswer(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='writing_user_answers')
    writing = models.ForeignKey(Writing, on_delete=models.CASCADE, related_name='user_answers')
    question_number = models.PositiveBigIntegerField(default=1)
    answer = models.TextField()
    
    feedback = RichTextField(blank=True, null=True)
    score = models.FloatField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Writing Answer'
        verbose_name_plural = 'Writing Answers'
        unique_together = ('user', 'writing')
        ordering = ['-created_at']

    def __str__(self):
        return f"Answer by {self.user.username} for {self.writing.writing_material.title}"
    
    @property
    def word_count(self):
        if not self.answer:
            return 0
        cleaned_text = re.sub(r'[.,!?;:"\'()\[\]{}*&^%$#@`~+=<>/\\|]', '', self.answer)
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        words = cleaned_text.split(' ')
        words = [word for word in words if word]

        return len(words)


