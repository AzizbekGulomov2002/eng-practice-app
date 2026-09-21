from rest_framework import serializers

from apps.app.models import Users
from apps.listening.models import ListeningAnswer, ListeningUserAnswer
from apps.listening.serializers import ListeningAnswerSerializer
from apps.reading.models import ReadingAnswer, ReadingUserAnswer
from apps.reading.serializers import ReadingAnswerSerializer
from apps.speaking.models import SpeakingUserAnswer
from apps.speaking.serializers import SpeakingAnswerSerializer
from apps.writing.models import WritingUserAnswer
from apps.writing.serializers import WritingAnswerCreateSerializer


class ReadingAnswerSerializer(serializers.ModelSerializer):
    test_title = serializers.CharField(source='reading.reading_material.test_material.test.title', read_only=True)
    test_number = serializers.CharField(source='reading.reading_material.test_material.test.test_number', read_only=True)
    passage_number = serializers.IntegerField(source='reading.passage_number', read_only=True)
    reading_title = serializers.CharField(source='reading.title', read_only=True)
    correct_answer = serializers.SerializerMethodField() # Added field

    class Meta:
        model = ReadingUserAnswer
        fields = ['question_number', 'answer', 'correct_answer', 'is_true', 'created_at', 'test_title', 'test_number', 'passage_number', 'reading_title']
        ref_name = 'ResultsReadingAnswer'

    def get_correct_answer(self, obj):
        try:
            correct_answer_obj = ReadingAnswer.objects.get(
                reading=obj.reading,
                question_number=obj.question_number
            )
            return correct_answer_obj.true_answer
        except ReadingAnswer.DoesNotExist:
            return None

class ListeningAnswerSerializer(serializers.ModelSerializer):
    test_title = serializers.CharField(source='listening.listening_material.test_material.test.title', read_only=True)
    test_number = serializers.CharField(source='listening.listening_material.test_material.test.test_number', read_only=True)
    section_number = serializers.IntegerField(source='listening.listening_section', read_only=True)
    listening_title = serializers.CharField(source='listening.title', read_only=True)
    correct_answer = serializers.SerializerMethodField() # Added field

    class Meta:
        model = ListeningUserAnswer
        fields = ['question_number', 'answer', 'correct_answer', 'is_true', 'created_at', 'test_title', 'test_number', 'section_number', 'listening_title']
        ref_name = 'ResultsListeningAnswer'

    def get_correct_answer(self, obj):
        try:
            correct_answer_obj = ListeningAnswer.objects.get(
                listening=obj.listening,
                question_number=obj.question_number
            )
            return correct_answer_obj.true_answer
        except ListeningAnswer.DoesNotExist:
            return None

class WritingAnswerSerializer(serializers.ModelSerializer):
    test_title = serializers.CharField(source='writing.writing_material.test_material.test.title', read_only=True)
    test_number = serializers.CharField(source='writing.writing_material.test_material.test.test_number', read_only=True)
    task_number = serializers.IntegerField(source='writing.writing_task', read_only=True)
    word_count = serializers.ReadOnlyField()

    class Meta:
        model = WritingUserAnswer
        fields = ['question_number', 'answer', 'feedback', 'score', 'created_at', 'test_title', 'test_number', 'task_number', 'word_count']
        ref_name = 'ResultsWritingAnswer'

class SpeakingAnswerSerializer(serializers.ModelSerializer):
    test_title = serializers.CharField(source='speaking.test_material.test.title', read_only=True)
    test_number = serializers.CharField(source='speaking.test_material.test.test_number', read_only=True)
    material_title = serializers.CharField(source='speaking.title', read_only=True)
    record = serializers.SerializerMethodField()
    questions = serializers.SerializerMethodField()
    question_number = serializers.SerializerMethodField()

    class Meta:
        model = SpeakingUserAnswer
        fields = ['question_number', 'record', 'feedback', 'score', 'created_at', 'test_title', 'test_number', 'material_title', 'questions']
        ref_name = 'ResultsSpeakingAnswer'

    def get_record(self, obj):
        record_file = obj.record
        if record_file and hasattr(record_file, 'url'):
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(record_file.url)
            return record_file.url
        return None

    def get_questions(self, obj):
        """
        Speaking material dagi barcha savollarni olish
        """
        questions_list = []
        
        # SpeakingMaterial dan barcha Speaking section larni olish
        speaking_sections = obj.speaking.speaking_sections.all()
        
        for section in speaking_sections:
            # Har bir section dagi savollarni olish
            section_questions = section.speaking_answer.all()
            for question in section_questions:
                questions_list.append({
                    'question_number': question.question_number,
                    'question': question.question,
                    'speaking_part': section.speaking_part
                })
        
        # Question number bo'yicha tartiblash
        questions_list.sort(key=lambda x: x['question_number'])
        return questions_list

    def get_question_number(self, obj):
        """
        Default question_number (SpeakingUserAnswer da question_number yo'q bo'lgani uchun)
        Agar specific question_number kerak bo'lsa, modelga qo'shish kerak
        """
        # Hozircha default 1 qayataramiz, agar kerak bo'lsa o'zgartirishingiz mumkin
        return 1


class StudentResultSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    group_name = serializers.CharField(source='student_group.name', read_only=True)
    reading_answers = ReadingAnswerSerializer(source='reading_user_answers', many=True, read_only=True)
    listening_answers = ListeningAnswerSerializer(source='listening_user_answers', many=True, read_only=True)
    writing_answers = WritingAnswerSerializer(source='writing_user_answers', many=True, read_only=True)
    speaking_answers = SpeakingAnswerSerializer(source='speaking_user_answers', many=True, read_only=True)

    # Statistics
    total_reading_score = serializers.SerializerMethodField()
    total_listening_score = serializers.SerializerMethodField()
    total_writing_score = serializers.SerializerMethodField()
    total_speaking_score = serializers.SerializerMethodField()

    class Meta:
        model = Users
        fields = [
            'id', 'full_name', 'phone', 'group_name',
            'reading_answers', 'listening_answers', 'writing_answers', 'speaking_answers',
            'total_reading_score', 'total_listening_score', 'total_writing_score', 'total_speaking_score'
        ]
        ref_name = 'ResultsStudentResult'

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    def get_total_reading_score(self, obj):
        correct_answers = obj.reading_user_answers.filter(is_true=True).count()
        total_answers = obj.reading_user_answers.count()
        return {'correct': correct_answers, 'total': total_answers}

    def get_total_listening_score(self, obj):
        correct_answers = obj.listening_user_answers.filter(is_true=True).count()
        total_answers = obj.listening_user_answers.count()
        return {'correct': correct_answers, 'total': total_answers}

    def get_total_writing_score(self, obj):
        scores = obj.writing_user_answers.exclude(score__isnull=True).values_list('score', flat=True)
        if scores:
            return {'average': sum(scores) / len(scores), 'count': len(scores)}
        return {'average': None, 'count': 0}

    def get_total_speaking_score(self, obj):
        scores = obj.speaking_user_answers.exclude(score__isnull=True).values_list('score', flat=True)
        if scores:
            return {'average': sum(scores) / len(scores), 'count': len(scores)}
        return {'average': None, 'count': 0}

class ResultsSummarySerializer(serializers.Serializer):
    """Serializer for aggregated results summary"""
    student_id = serializers.IntegerField()
    full_name = serializers.CharField()
    phone = serializers.CharField()
    group_name = serializers.CharField()

    # Test statistics
    tests_taken = serializers.IntegerField()
    last_activity = serializers.DateTimeField(allow_null=True)

    # Score summaries
    reading_score = serializers.DictField()
    listening_score = serializers.DictField()
    writing_avg_score = serializers.FloatField(allow_null=True)
    speaking_avg_score = serializers.FloatField(allow_null=True)

class SimpleStudentSerializer(serializers.ModelSerializer):
    """Simple serializer for basic student info"""
    full_name = serializers.SerializerMethodField()
    group_name = serializers.CharField(source='student_group.name', read_only=True)

    class Meta:
        model = Users
        fields = ['id', 'full_name', 'phone', 'group_name']
        ref_name = 'ResultsSimpleStudent'

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"




##############
class MaterialSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    type = serializers.CharField()
    title = serializers.CharField()
    is_completed = serializers.BooleanField(required=False)
    score = serializers.FloatField(required=False)
    feedback = serializers.CharField(required=False)

class StudentResultSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    phone = serializers.CharField()
    group_name = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    materials = serializers.SerializerMethodField()
    
    # Conditional fields for reading and listening only
    total_questions = serializers.SerializerMethodField()
    correct_answers = serializers.SerializerMethodField()
    incorrect_answers = serializers.SerializerMethodField()
    score_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = Users
        fields = [
            'id', 'full_name', 'phone', 'group_name', 
            'total_questions', 'correct_answers', 'incorrect_answers', 
            'score_percentage', 'created_at', 'materials'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Remove statistical fields if not reading or listening
        result_type = self.context.get('result_type', 'full')
        if result_type not in ['reading', 'listening']:
            # Remove these fields for writing, speaking, or full type
            if result_type in ['writing', 'speaking']:
                self.fields.pop('total_questions', None)
                self.fields.pop('correct_answers', None) 
                self.fields.pop('incorrect_answers', None)
                self.fields.pop('score_percentage', None)
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    
    def get_group_name(self, obj):
        return obj.student_group.name if obj.student_group else ""
    
    def get_created_at(self, obj):
        # Get the earliest answer date for this student
        earliest_date = None
        
        # Check listening answers
        listening_date = obj.listening_user_answers.first()
        if listening_date:
            earliest_date = listening_date.created_at
            
        # Check reading answers  
        reading_date = obj.reading_user_answers.first()
        if reading_date and (not earliest_date or reading_date.created_at < earliest_date):
            earliest_date = reading_date.created_at
            
        # Check writing answers
        writing_date = obj.writing_user_answers.first()
        if writing_date and (not earliest_date or writing_date.created_at < earliest_date):
            earliest_date = writing_date.created_at
            
        # Check speaking answers
        speaking_date = obj.speaking_user_answers.first()
        if speaking_date and (not earliest_date or speaking_date.created_at < earliest_date):
            earliest_date = speaking_date.created_at
        
        return earliest_date.strftime("%Y-%m-%d-%H:%M") if earliest_date else None
    
    def _get_material_stats(self, obj, material_type):
        """Helper method to get statistics for a specific material type"""
        stats = {'total': 0, 'correct': 0}
        
        if material_type == 'listening':
            answers = obj.listening_user_answers.all()
            stats['total'] = answers.count()
            stats['correct'] = answers.filter(is_true=True).count()
        elif material_type == 'reading':
            answers = obj.reading_user_answers.all()
            stats['total'] = answers.count()
            stats['correct'] = answers.filter(is_true=True).count()
            
        return stats
    
    def get_total_questions(self, obj):
        result_type = self.context.get('result_type', 'full')
        
        if result_type == 'listening':
            return self._get_material_stats(obj, 'listening')['total']
        elif result_type == 'reading':
            return self._get_material_stats(obj, 'reading')['total']
            
        return 0
    
    def get_correct_answers(self, obj):
        result_type = self.context.get('result_type', 'full')
        
        if result_type == 'listening':
            return self._get_material_stats(obj, 'listening')['correct']
        elif result_type == 'reading':
            return self._get_material_stats(obj, 'reading')['correct']
            
        return 0
    
    def get_incorrect_answers(self, obj):
        total = self.get_total_questions(obj)
        correct = self.get_correct_answers(obj)
        return max(0, total - correct)
    
    def get_score_percentage(self, obj):
        total = self.get_total_questions(obj)
        correct = self.get_correct_answers(obj)
        
        if total == 0:
            return 0
        
        return round((correct / total) * 100)
    
    def get_materials(self, obj):
        test_accept = self.context.get('test_accept')
        result_type = self.context.get('result_type', 'full')
        materials = []
        
        if not test_accept:
            return materials
        
        # Get listening materials (with is_completed)
        if result_type in ['full', 'listening']:
            listening_materials = test_accept.listening_materials.all()
            for material in listening_materials:
                user_answers = obj.listening_user_answers.filter(
                    listening__listening_material=material
                ).exists()
                
                materials.append({
                    'id': material.id,
                    'type': 'listening',
                    'title': material.title or material.test_material.title,
                    'is_completed': user_answers
                })
        
        # Get reading materials (with is_completed)
        if result_type in ['full', 'reading']:
            reading_materials = test_accept.reading_materials.all()
            for material in reading_materials:
                user_answers = obj.reading_user_answers.filter(
                    reading__reading_material=material
                ).exists()
                
                materials.append({
                    'id': material.id,
                    'type': 'reading', 
                    'title': material.title or material.test_material.title,
                    'is_completed': user_answers
                })
        
        # Get writing materials (with score and feedback)
        if result_type in ['full', 'writing']:
            writing_materials = test_accept.writing_materials.all()
            for material in writing_materials:
                user_answer = obj.writing_user_answers.filter(
                    writing__writing_material=material
                ).first()
                
                material_data = {
                    'id': material.id,
                    'type': 'writing',
                    'title': material.title or material.test_material.title,
                }
                
                if user_answer:
                    material_data['score'] = user_answer.score
                    material_data['feedback'] = user_answer.feedback
                else:
                    material_data['score'] = None
                    material_data['feedback'] = None
                
                materials.append(material_data)
        
        # Get speaking materials (with score and feedback)
        if result_type in ['full', 'speaking']:
            speaking_materials = test_accept.speaking_materials.all()
            for material in speaking_materials:
                # Speaking user answer is linked to SpeakingMaterial directly
                user_answer = obj.speaking_user_answers.filter(
                    speaking=material
                ).first()
                
                material_data = {
                    'id': material.id,
                    'type': 'speaking',
                    'title': material.title or material.test_material.title,
                }
                
                if user_answer:
                    material_data['score'] = user_answer.score
                    material_data['feedback'] = user_answer.feedback
                else:
                    material_data['score'] = None
                    material_data['feedback'] = None
                
                materials.append(material_data)
        
        return materials

