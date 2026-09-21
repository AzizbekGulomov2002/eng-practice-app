from rest_framework import serializers
from apps.speaking.models import SpeakingMaterial
from apps.writing.models import WritingMaterial
from .models import Reading, ReadingAnswer, ReadingMaterial, ReadingUserAnswer

class ReadingAnswerSerializer(serializers.ModelSerializer):
    user_ids = serializers.PrimaryKeyRelatedField(
        source='user',
        many=True,
        read_only=True
    )
    user_names = serializers.SerializerMethodField()

    class Meta:
        model = ReadingAnswer
        fields = ['id', 'question_number', 'question_type', 'user_ids', 'user_names']
        read_only_fields = ['question_number', 'question_type', 'user_ids', 'user_names']

    def get_user_names(self, obj):
        return [str(u) for u in obj.user.all()]

class StudentReadingAnswerSerializer(serializers.ModelSerializer):
    test_material_id = serializers.IntegerField(source='reading.test_material.id', read_only=True)
    test_material_title = serializers.CharField(source='reading.test_material.title', read_only=True)
    test_material_type = serializers.CharField(source='reading.test_material.test_type', read_only=True)

    reading_id = serializers.IntegerField(source='reading.id', read_only=True)
    reading_title = serializers.CharField(source='reading.title', read_only=True)

    class Meta:
        model = ReadingUserAnswer
        fields = (
            'id',
            'test_material_id',
            'test_material_title',
            'test_material_type',
            'reading_id',
            'reading_title',
            'question_number',
            'answer',
            'is_true',
        )
        
        
class ReadingAnswersSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReadingAnswer
        fields = ['id', 'question_number']



class ReadingSectionSerializer(serializers.ModelSerializer):
    question_numbers = ReadingAnswersSerializer(source='answers', many=True, read_only=True)
    questions = serializers.SerializerMethodField()
    
    class Meta:
        model = Reading
        fields = [
            'id',
            'title',
            'passage_number',
            'description',
            'content',
            'questions',
            'created_at',
            'question_numbers'
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



class ReadingSerializer(serializers.ModelSerializer):
    reading_passages = ReadingSectionSerializer(source='reading_materials', many=True, read_only=True)

    class Meta:
        model = ReadingMaterial
        fields = [
            'id',
            'title',
            'answer_time',
            'reading_passages'
        ]


class ReadingMaterialDetailSerializer(serializers.ModelSerializer):
    reading_parts = ReadingSectionSerializer(source='reading_materials', many=True, read_only=True)
    test_type = serializers.SerializerMethodField()
    is_view = serializers.SerializerMethodField()
    material = serializers.SerializerMethodField()

    class Meta:
        model = ReadingMaterial
        fields = [
            'id',
            'title',
            'answer_time',
            'reading_parts',
            "test_type",
            "is_view",
            "material",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)

        # Check if test_type is "Thematic" and exclude specific fields
        if data.get('test_type') == 'Thematic':
            data.pop('test_type', None)
            data.pop('is_view', None)
            data.pop('material', None)

        return data

    def get_test_type(self, obj):
        return obj.test_material.test.test_type if obj.test_material and obj.test_material.test else None

    def get_is_view(self, obj):
        return obj.test_material.is_view if obj.test_material else None

    def get_material(self, obj):
        test_material = obj.test_material
        writing_material = WritingMaterial.objects.filter(test_material=test_material).first()
        speaking_material = SpeakingMaterial.objects.filter(test_material=test_material).first()

        next_test = None
        next_test_id = None

        if writing_material:
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


class ReadingMaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReadingMaterial
        fields = [
            'id',
            'title',
            'answer_time',
        ]


class ReadingDetailSerializer(serializers.ModelSerializer):
    test_material_id = serializers.IntegerField(
        source='reading_material.test_material.id',
        read_only=True
    )

    test_material_number = serializers.CharField(
        source='reading_material.test_material.test_number',
        read_only=True
    )
    questions = serializers.SerializerMethodField()

    class Meta:
        model = Reading
        fields = [
            'id',
            'title',
            'test_material_id',
            'test_material_number',
            'passage_number',
            'created_at',
            'description',
            'content',
            'questions',
        ]
        read_only_fields = ['created_at', 'test_material_id', 'test_material_number']
    
    def get_questions(self, obj):
        """Return questions based on user's is_parse setting"""
        request = self.context.get('request')
        if request and request.user and hasattr(request.user, 'is_parse'):
            if not request.user.is_parse:
                # Return original unparsed questions if available
                return obj.questions_raw if obj.questions_raw else obj.questions
        # Default: return parsed questions
        return obj.questions


class ReadingAnswerListSerializer(serializers.ListSerializer):
    def validate(self, attrs):
        user = self.context['request'].user
        reading = self.context.get('reading')

        if not reading:
            raise serializers.ValidationError("Kontekstda 'reading' topilmadi.")
        incoming_question_numbers = [item['question_number'] for item in attrs]
        if len(incoming_question_numbers) != len(set(incoming_question_numbers)):
            raise serializers.ValidationError("So'rov ichida bir xil savol raqami bir necha marta yuborilgan.")
        existing_answers = ReadingUserAnswer.objects.filter(
            user=user,
            reading=reading,
            question_number__in=incoming_question_numbers
        )

        if existing_answers.exists():
            answered_questions = list(existing_answers.values_list('question_number', flat=True))
            raise serializers.ValidationError(
                f"Bu savollarga allaqachon javob berilgan: {answered_questions}"
            )

        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        reading = self.context['reading']
        answers_to_create = [
            ReadingUserAnswer(user=user, reading=reading, **item)
            for item in validated_data
        ]
        
        created_answers = ReadingUserAnswer.objects.bulk_create(answers_to_create)
        for answer in created_answers:
            answer.save() 
        return created_answers



class ReadingUserAnswerSerializer(serializers.ModelSerializer):
    reading_id = serializers.IntegerField(write_only=True)
    question_number = serializers.IntegerField()
    answer = serializers.CharField(max_length=200, required=False, allow_blank=True, allow_null=True)
    true_answer = serializers.SerializerMethodField()
    is_true = serializers.BooleanField(read_only=True)

    class Meta:
        model = ReadingUserAnswer
        fields = ('id', 'reading_id', 'question_number', 'answer', 'true_answer', 'is_true', 'created_at')
        read_only_fields = ('id', 'true_answer', 'is_true', 'created_at')

    def get_true_answer(self, obj):
        try:
            reading_answer = ReadingAnswer.objects.get(
                reading=obj.reading,
                question_number=obj.question_number
            )
            return reading_answer.true_answer
        except ReadingAnswer.DoesNotExist:
            return None

    def create(self, validated_data):
        user = self.context['request'].user
        reading_id = validated_data.pop("reading_id")
        try:
            reading = Reading.objects.get(id=reading_id)
        except Reading.DoesNotExist:
            raise serializers.ValidationError({"reading_id": f"Reading with id {reading_id} not found"})
        return ReadingUserAnswer.objects.create(
            user=user,
            reading=reading,
            **validated_data
        )

