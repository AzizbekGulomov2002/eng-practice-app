from rest_framework import generics, viewsets, permissions
from rest_framework.response import Response
from rest_framework import generics, serializers, permissions
from drf_yasg.utils import swagger_auto_schema
from apps.app.middleware import IsAllowedIP
from rest_framework.views import APIView
from rest_framework import status
import logging
logger = logging.getLogger(__name__)
from django.db import transaction, IntegrityError

from .models import Listening, ListeningAnswer, ListeningMaterial, ListeningUserAnswer
from .serializers import (
    ListeningMaterialDetailSerializer,
    ListeningAnswerSerializer,
    ListeningUserAnswerSerializer,
)


class ListeningViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ListeningMaterial.objects.all().prefetch_related('listening_sections')
    serializer_class = ListeningMaterialDetailSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class ListeningByMaterialView(generics.RetrieveAPIView):
    queryset = ListeningMaterial.objects.all().prefetch_related(
        'listening_sections__answers' )
    serializer_class = ListeningMaterialDetailSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]



class ListeningAnswerView(generics.RetrieveAPIView):
    queryset = ListeningAnswer.objects.all()
    serializer_class = ListeningAnswerSerializer
    lookup_field = 'id'
    permission_classes = [permissions.IsAuthenticated]



class ListeningUserAnswerListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAllowedIP]

    @swagger_auto_schema(
        request_body=ListeningUserAnswerSerializer(many=True),
        responses={201: ListeningUserAnswerSerializer(many=True)}
    )
    def post(self, request, material_id):
        user = request.user  

        # 0. Tekshiruv — user allaqachon javob berganmi?
        already_exists = ListeningUserAnswer.objects.filter(
            user=user,
            listening__listening_material_id=material_id
        ).exists()

        if already_exists:
            return Response(
                {"error": "You have already submitted answers for this material."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ListeningUserAnswerSerializer(
            data=request.data, 
            many=True, 
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # 1. Validate ListeningMaterial
        try:
            material = ListeningMaterial.objects.get(id=material_id)
        except ListeningMaterial.DoesNotExist:
            logger.error(f"ListeningMaterial with id {material_id} not found")
            return Response(
                {"error": "Listening material not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # 2. Validate listening_ids belong to material
        valid_listenings = material.listening_sections.values_list("id", flat=True)
        for item in data:
            if item["listening_id"] not in valid_listenings:
                logger.error(f"Listening ID {item['listening_id']} not in material {material_id}")
                return Response(
                    {"error": f"Listening ID {item['listening_id']} does not belong to material {material_id}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # 3. Check for duplicates in request data
        seen = set()
        for item in data:
            key = (item["listening_id"], item["question_number"])
            if key in seen:
                return Response(
                    {
                        "error": "Duplicate entries in request",
                        "details": f"Multiple answers for listening_id: {item['listening_id']}, question_number: {item['question_number']}"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            seen.add(key)

        # 4. Save answers (birinchi marta yozilayotganda)
        saved_answers = []
        try:
            with transaction.atomic():
                for item in data:
                    listening = Listening.objects.get(id=item["listening_id"])
                    obj = ListeningUserAnswer.objects.create(
                        user=user,
                        listening=listening,
                        question_number=item["question_number"],
                        answer=item.get("answer")
                    )
                    saved_answers.append(obj)
        except IntegrityError:
            logger.error(f"Database error while saving answers for material {material_id}")
            return Response(
                {
                    "error": "Database error",
                    "details": "Something went wrong while saving answers."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # 5. Calculate totals (o'zgarmaydi)
        all_user_answers_for_material = ListeningUserAnswer.objects.filter(
            user=user,
            listening__listening_material=material
        )

        total_answers = all_user_answers_for_material.count()
        total_correct_answers = all_user_answers_for_material.filter(is_true=True).count()
        total_incorrect_answers = total_answers - total_correct_answers
        percentage_correct = 0
        if total_answers > 0:
            percentage_correct = (total_correct_answers / total_answers) * 100

        # 6. Calculate overall listening score (o‘zgarmaydi)
        overall_listening_score = None
        test_type = material.test_material.test.test_type
        if test_type == 'mock':
            total_possible_questions = ListeningAnswer.objects.filter(
                listening__listening_material=material
            ).count()

            if total_possible_questions == 40:
                correct_answers_count_for_score = total_correct_answers
                if correct_answers_count_for_score >= 39:
                    overall_listening_score = 9.0
                elif correct_answers_count_for_score >= 37:
                    overall_listening_score = 8.5
                elif correct_answers_count_for_score >= 35:
                    overall_listening_score = 8.0
                elif correct_answers_count_for_score >= 33:
                    overall_listening_score = 7.5
                elif correct_answers_count_for_score >= 30:
                    overall_listening_score = 7.0
                elif correct_answers_count_for_score >= 27:
                    overall_listening_score = 6.5
                elif correct_answers_count_for_score >= 23:
                    overall_listening_score = 6.0
                elif correct_answers_count_for_score >= 19:
                    overall_listening_score = 5.5
                elif correct_answers_count_for_score >= 15:
                    overall_listening_score = 5.0
                elif correct_answers_count_for_score >= 13:
                    overall_listening_score = 4.5
                elif correct_answers_count_for_score >= 10:
                    overall_listening_score = 4.0
                else:
                    overall_listening_score = 0.0
            else:
                overall_listening_score = f"N/A - Total questions for Mock test expected 40, but found {total_possible_questions}"

        # 7. Prepare response
        response_serializer = ListeningUserAnswerSerializer(all_user_answers_for_material, many=True)
        response_data = {
            "answers": response_serializer.data,
            "total_answers": total_answers,
            "total_correct_answers": total_correct_answers,
            "total_incorrect_answers": total_incorrect_answers,
            "percentage_correct_for_material": round(percentage_correct, 2),
            "test_type": test_type,
            "overall_score": overall_listening_score,
        }
        
        logger.info(f"Successfully processed {len(saved_answers)} answers for material {material_id}")
        return Response(response_data, status=status.HTTP_201_CREATED)


    
