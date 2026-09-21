from rest_framework import viewsets, generics, permissions
from rest_framework import mixins
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import IntegrityError

from apps.app.middleware import IsAllowedIP
from .models import Writing, WritingAnswer, WritingMaterial, WritingUserAnswer
from .serializers import (
    WritingAnswerCreateSerializer,
    WritingMaterialDetailSerializer,
    WritingMaterialSerializer,
)
class WritingViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WritingMaterial.objects.all()
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return WritingMaterialDetailSerializer
        return WritingMaterialSerializer


class WritingByMaterialView(generics.RetrieveAPIView):
    queryset = WritingMaterial.objects.all().prefetch_related('writing_materials__writing_answers')
    serializer_class = WritingMaterialDetailSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_object(self):
        material_id = self.kwargs.get('test_material_id')
        return get_object_or_404(self.queryset, pk=material_id)
   

class WritingAnswersView(
    mixins.ListModelMixin,
    generics.GenericAPIView
):
    permission_classes = [permissions.IsAuthenticated, IsAllowedIP]

    def get_serializer_class(self):
        return WritingAnswerCreateSerializer

    def get_queryset(self):
        test_material_id = self.kwargs["test_material_id"]
        # Faqat shu userning javoblarini qaytaradi
        return WritingUserAnswer.objects.filter(
            writing__writing_material__test_material_id=test_material_id,
            user=self.request.user
        )

    def get_serializer_context(self):
        return {"request": self.request}

    # GET /writing-answers/<test_material_id>/
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    # POST /writing-answers/<test_material_id>/
    def post(self, request, *args, **kwargs):
        test_material_id = self.kwargs["test_material_id"]
        user = request.user

        # Request data dan writing ID larni olamiz
        many = isinstance(request.data, list)
        if many:
            writing_ids = [item.get('writing') for item in request.data if item.get('writing')]
        else:
            writing_ids = [request.data.get('writing')] if request.data.get('writing') else []

        # Har bir writing ID uchun mavjud javobni tekshiramiz
        for writing_id in writing_ids:
            if WritingUserAnswer.objects.filter(user=user, writing_id=writing_id).exists():
                return Response(
                    {"error": "You have already submitted answers for this material."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

        # Agar javob yo'q bo'lsa, yangi yozuv yaratadi
        try:
            serializer = self.get_serializer(data=request.data, many=many)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except IntegrityError:
            # Agar IntegrityError bo'lsa, mavjud javob borligini bildiradi
            return Response(
                {"error": "You have already submitted answers for this material."},
                status=status.HTTP_401_UNAUTHORIZED,
            )


    def perform_create(self, serializer):
        # Har doim user ni serializer.save() ga yuborish kerak
        serializer.save(user=self.request.user)



