from rest_framework import serializers
from apps.speaking.models import SpeakingMaterial, Speaking, SpeakingAnswer, SpeakingUserAnswer


class SpeakingAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpeakingAnswer
        fields = ['id', 'question_number', 'question']

class SpeakingSectionSerializer(serializers.ModelSerializer):
    question_numbers = SpeakingAnswerSerializer(many=True, read_only=True, source='speaking_answer')

    class Meta:
        model = Speaking
        fields = [
            'id',
            'speaking_part',
            'prep_time',
            'answer_time',
            'comment',
            'description',
            'question_numbers',
        ]



class SpeakingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpeakingMaterial
        fields = ['id', 'title', 'test_material']
        


class SpeakingMaterialSerializer(serializers.ModelSerializer):
    speaking_parts = SpeakingSectionSerializer(many=True, read_only=True, source='speaking_sections')

    class Meta:
        model = SpeakingMaterial
        fields = ['id', 'title', 'test_material', 'speaking_parts']


class SpeakingUserAnswerSerializer(serializers.ModelSerializer):
    record = serializers.SerializerMethodField()
    speaking_part = serializers.IntegerField(source="speaking.speaking_part", read_only=True)

    class Meta:
        model = SpeakingUserAnswer
        fields = ["id", "speaking", "speaking_part", "record", "feedback"]
        read_only_fields = ["id", "speaking_part","feedback","score", "record"]
    
    def get_record(self, obj):
        """Return record with URL and MIME type for proper webm duration display"""
        if obj.record and hasattr(obj.record, 'url'):
            import mimetypes
            request = self.context.get('request')
            url = request.build_absolute_uri(obj.record.url) if request else obj.record.url
            
            # WebM fayllar uchun to'g'ri MIME type ni aniqlash
            file_name = str(obj.record.name).lower()
            mime_type, _ = mimetypes.guess_type(obj.record.url)
            if file_name.endswith('.webm'):
                mime_type = "audio/webm"
            elif not mime_type:
                mime_type = "audio/mpeg"
            
            return {
                'url': url,
                'mime_type': mime_type,
                'file_name': obj.record.name
            }
        return None

