from rest_framework import generics, permissions, views
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.shortcuts import get_object_or_404

from rest_framework import parsers,status
from apps.app.middleware import IsAllowedIP
from apps.speaking.models import Speaking, SpeakingAnswer, SpeakingMaterial, SpeakingUserAnswer
from apps.speaking.serializers import (
    SpeakingSerializer,
    SpeakingAnswerSerializer,
    SpeakingUserAnswerSerializer,
    SpeakingMaterialSerializer
)
from apps.speaking.utils import convert_audio_to_mp3_sync

class SpeakingByMaterialView(generics.RetrieveAPIView):
    queryset = SpeakingMaterial.objects.all().prefetch_related('speaking_sections__speaking_answer')
    serializer_class = SpeakingMaterialSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_object(self):
        material_id = self.kwargs.get('test_material_id')
        return get_object_or_404(self.queryset, pk=material_id)
    
class SpeakingsViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly] 
    serializer_class = SpeakingSerializer
    queryset = SpeakingMaterial.objects.prefetch_related('speaking_sections')



# 2. Get answers for a specific speaking
class SpeakingAnswerListView(generics.ListAPIView):
    serializer_class = SpeakingAnswerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        speaking_id = self.kwargs["speaking_id"]
        return SpeakingAnswer.objects.filter(speaking_id=speaking_id)




class SpeakingUserAnswerCreateView(generics.CreateAPIView):
    serializer_class = SpeakingUserAnswerSerializer
    permission_classes = [permissions.IsAuthenticated, IsAllowedIP]
    parser_classes = [parsers.MultiPartParser]

    def get_queryset(self):
        return SpeakingUserAnswer.objects.filter(user=self.request.user)

    @swagger_auto_schema(
        operation_description="Upload speaking answer (student only)",
        manual_parameters=[
            openapi.Parameter(
                name="speaking",
                in_=openapi.IN_FORM,
                type=openapi.TYPE_INTEGER,
                required=True,
                description="Speaking ID"
            ),
            openapi.Parameter(
                name="record",
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                required=True,
                description="Audio file"
            ),
        ],
        responses={201: SpeakingUserAnswerSerializer}
    )
    def create(self, request, *args, **kwargs):
        user = request.user
        speaking_id = request.data.get('speaking')
        record_file = request.data.get('record')

        # Basic validation
        if not speaking_id or not record_file:
            return Response(
                {"error": "Speaking ID and record file are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # SpeakingMaterial instance tekshirish
        try:
            speaking_instance = SpeakingMaterial.objects.get(pk=speaking_id)
        except SpeakingMaterial.DoesNotExist:
            return Response(
                {"error": "Speaking test not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # User oldin topshirganmi?
        already_exists = SpeakingUserAnswer.objects.filter(
            user=user, speaking=speaking_instance
        ).exists()

        if already_exists:
            return Response(
                {"error": "You have already submitted an answer for this speaking test."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Yangi javob yaratish
        obj = SpeakingUserAnswer.objects.create(
            user=user,
            speaking=speaking_instance,
            record=record_file
        )

        # Saqlangan faylni tekshirib, aniq MP3 formatga o'giramiz (nomiga qarab emas, serverdagi faylga qarab)
        current_name = str(obj.record.name).lower() if obj.record and obj.record.name else ""
        if not current_name.endswith(".mp3"):
            convert_audio_to_mp3_sync(obj)
            obj.refresh_from_db()  # convert qilingan MP3 fayl bilan instance ni yangilaymiz

        serializer = self.get_serializer(obj)
        return Response(serializer.data, status=status.HTTP_201_CREATED)



