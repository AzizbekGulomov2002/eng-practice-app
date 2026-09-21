from rest_framework import serializers

from apps.speaking.models import  SpeakingMaterial
from .models import Writing, WritingAnswer, WritingMaterial, WritingUserAnswer


class WritingQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WritingAnswer  
        fields = ["id", "question_number", "question"]


class WritingSerializer(serializers.ModelSerializer):
    writing_questions = WritingQuestionSerializer(source="writing_answers", many=True, read_only=True)

    class Meta:
        model = Writing
        fields = [
            "id",
            "writing_task",
            "description",
            "created_at",
            "writing_questions",
        ]

class WritingTaskSerializer(serializers.ModelSerializer):
    writing_questions = WritingQuestionSerializer(source="writing_answers", many=True, read_only=True)

    class Meta:
        model = Writing
        fields = ["id", "writing_task", "description", "created_at", "writing_questions"]

class WritingMaterialDetailSerializer(serializers.ModelSerializer):
    writing_parts = WritingTaskSerializer(source="writing_materials", many=True, read_only=True)
    material = serializers.SerializerMethodField()
    is_view = serializers.SerializerMethodField()
    
    class Meta:
        model = WritingMaterial
        fields = ["id", "title", "answer_time", "writing_parts", "material", 'is_view']
        
    def get_is_view(self, obj):
        return obj.test_material.is_view if obj.test_material else None
        
    def get_material(self, obj):
        test_material = obj.test_material
        speaking_material = SpeakingMaterial.objects.filter(test_material=test_material).first()

        next_test = None
        next_test_id = None

        # Writing dan keyin Speaking
        if speaking_material:
            next_test = "speaking"
            next_test_id = speaking_material.id

        return {
            "next_test": next_test,
            "next_test_id": next_test_id,
            "test_type": test_material.test.test_type if test_material and test_material.test else None,
        }



class WritingMaterialSerializer(serializers.ModelSerializer):
    writing_parts = WritingSerializer(source="writing_materials", many=True, read_only=True)

    class Meta:
        model = WritingMaterial
        fields = [
            "id",
            "title",
            "test_material",
            "writing_parts",
        ]


class WritingAnswerListSerializer(serializers.ListSerializer):
    def create(self, validated_data):
        results = []
        for item in validated_data:
            # Use the child serializer to validate & create each item
            serializer = WritingAnswerCreateSerializer(
                data=item,
                context=self.context
            )
            serializer.is_valid(raise_exception=True)
            # Pass user from context to serializer.save()
            results.append(serializer.save(user=self.context['request'].user))
        return results


class WritingAnswerCreateSerializer(serializers.ModelSerializer):
    writing = serializers.IntegerField(write_only=True)
    answer = serializers.CharField(allow_blank=True, required=False)

    class Meta:
        model = WritingUserAnswer
        fields = ["writing", "question_number", "answer"]
        read_only_fields = ["user", "feedback", "score"]
        list_serializer_class = WritingAnswerListSerializer

    def validate_writing(self, value):
        # optional: validate that writing exists and belongs to test_material in URL
        try:
            writing_obj = Writing.objects.get(pk=value)
        except Writing.DoesNotExist:
            raise serializers.ValidationError(f"Writing with id {value} does not exist.")
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        writing_pk = validated_data.pop('writing')
        try:
            writing = Writing.objects.get(pk=writing_pk)
        except Writing.DoesNotExist:
            raise serializers.ValidationError({"writing": f"Writing with id {writing_pk} not found"})

        question_number = validated_data.get('question_number', 1)
        answer = validated_data.get('answer', '')

        # Agar mavjud javob bo'lsa xato qaytaradi (blank javob ham hisoblanadi)
        if WritingUserAnswer.objects.filter(user=user, writing=writing).exists():
            raise serializers.ValidationError(
                {"error": "You have already submitted answers for this material."}
            )

        # Yangi javob yaratamiz (blank bo'lsa ham)
        writing_answer = WritingUserAnswer.objects.create(
            user=user,
            writing=writing,
            question_number=question_number,
            answer=answer
        )

        return writing_answer






