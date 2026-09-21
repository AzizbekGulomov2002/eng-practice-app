from rest_framework import serializers
from django.utils.safestring import mark_safe

from apps.reading.models import ReadingMaterial
from apps.speaking.models import SpeakingMaterial
from apps.writing.models import WritingMaterial
from .models import Listening, ListeningMaterial, ListeningAnswer, ListeningUserAnswer


class ListeningAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListeningAnswer
        fields = ['id', 'listening', 'question_number', 'true_answer']

class ListeningsAnswerListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListeningAnswer
        fields = ['id', 'question_number']

class ListeningSectionSerializer(serializers.ModelSerializer):
    question_numbers = ListeningsAnswerListSerializer(source='answers', many=True, read_only=True)
    questions = serializers.SerializerMethodField()
    
    class Meta:
        model = Listening
        fields = [
            'id', 'title', 'listening_section', 'questions', 'audio',
            'audioscript', 'description', 'created_at', 'is_script', 'question_numbers'
        ]
    
    def get_questions(self, obj):
        """Return questions based on user's is_parse setting"""
        request = self.context.get('request')
        if request and request.user and hasattr(request.user, 'is_parse'):
            if not request.user.is_parse:
                # Return original unparsed questions if available
                return obj.questions_raw if obj.questions_raw else obj.questions
        # Default: return parsed questions
        return obj.questions
    
    def to_representation(self, instance):
        """Override to mark questions as safe HTML"""
        data = super().to_representation(instance)
        if 'questions' in data and data['questions']:
            data['questions'] = mark_safe(data['questions'])
        return data
        
        
class ListeningMaterialDetailSerializer(serializers.ModelSerializer):
    listening_parts = ListeningSectionSerializer(source='listening_sections', many=True, read_only=True)
    is_view = serializers.SerializerMethodField()
    material = serializers.SerializerMethodField()

    class Meta:
        model = ListeningMaterial
        fields = [
            'id',
            'title',
            'answer_time',
            'listening_parts',
            'is_view',
            'material'
        ]

    def get_is_view(self, obj):
        return obj.test_material.is_view if obj.test_material else None

    def get_material(self, obj):
        test_material = obj.test_material
        reading_material = ReadingMaterial.objects.filter(test_material=test_material).first()
        writing_material = WritingMaterial.objects.filter(test_material=test_material).first()
        speaking_material = SpeakingMaterial.objects.filter(test_material=test_material).first()

        next_test = None
        next_test_id = None

        # Listening dan keyin Reading, Writing, Speaking tartibida
        if reading_material:
            next_test = "reading"
            next_test_id = reading_material.id
        elif writing_material:
            next_test = "writing"
            next_test_id = writing_material.id
        elif speaking_material:
            next_test = "speaking"
            next_test_id = speaking_material.id

        return {
            "next_test": next_test,
            "next_test_id": next_test_id,
            "test_type": test_material.test.test_type if test_material and test_material.test else None,
        }






class ListeningUserAnswerSerializer(serializers.ModelSerializer):
    listening_id = serializers.IntegerField(write_only=True)
    question_number = serializers.IntegerField()
    answer = serializers.CharField(max_length=200, required=False, allow_blank=True, allow_null=True)
    true_answer = serializers.SerializerMethodField()
    is_true = serializers.BooleanField(read_only=True)

    class Meta:
        model = ListeningUserAnswer
        fields = ('id', 'listening_id', 'question_number', 'answer', 'true_answer', 'is_true', 'created_at')
        read_only_fields = ('id', 'true_answer', 'is_true', 'created_at')

    def get_true_answer(self, obj):
        try:
            listening_answer = ListeningAnswer.objects.get(
                listening=obj.listening,
                question_number=obj.question_number
            )
            return listening_answer.true_answer
        except ListeningAnswer.DoesNotExist:
            return None

    def create(self, validated_data):
        user = self.context['request'].user
        listening_id = validated_data.pop("listening_id")

        try:
            listening = Listening.objects.get(id=listening_id)
        except Listening.DoesNotExist:
            raise serializers.ValidationError({"listening_id": f"Listening with id {listening_id} not found"})

        return ListeningUserAnswer.objects.create(
            user=user,
            listening=listening,
            **validated_data
        )
    
    
class ListeningAnswerUpdateSerializer(serializers.Serializer):
    question_number = serializers.IntegerField()
    answer = serializers.CharField()


class ListeningSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listening
        fields = ['id', 'title', 'listening_section']

