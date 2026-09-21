from django.shortcuts import render
from rest_framework import generics, viewsets
from rest_framework.mixins import ListModelMixin
from drf_yasg.utils import swagger_auto_schema
from rest_framework.response import Response
from django.db import transaction, IntegrityError
from django.db.models import Prefetch


from apps.app.middleware import IsAllowedIP
from .models import Reading, ReadingAnswer, ReadingMaterial, ReadingUserAnswer
from .serializers import ReadingAnswerSerializer, ReadingSerializer, ReadingMaterialDetailSerializer, ReadingUserAnswerSerializer
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status

def index_view(request):
    return render(request, "index.html")

class ReadingViewSet(ListModelMixin, viewsets.GenericViewSet):
    serializer_class = ReadingSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    queryset = ReadingMaterial.objects.all().prefetch_related('reading_materials')
    
    
    
class ReadingByMaterialView(generics.RetrieveAPIView):
    queryset = ReadingMaterial.objects.all().prefetch_related(
        Prefetch(
            'reading_materials',
            queryset=Reading.objects.order_by('created_at')
        ),
        'reading_materials__answers'
    )
    serializer_class = ReadingMaterialDetailSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    
    

class ReadingAnswerView(generics.RetrieveUpdateAPIView):
    queryset = ReadingAnswer.objects.all()
    serializer_class = ReadingAnswerSerializer
    lookup_field = 'id'
    permission_classes = [IsAuthenticated]

    def perform_update(self, serializer):
        serializer.save()



class ReadingByTestMaterialListView(generics.ListAPIView):
    serializer_class = ReadingSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        test_material_id = self.kwargs['test_material_id']
        return Reading.objects.filter(test_material_id=test_material_id).order_by('passage_number')


class ReadingUserAnswerListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAllowedIP]

    @swagger_auto_schema(
        request_body=ReadingUserAnswerSerializer(many=True),
        responses={201: ReadingUserAnswerSerializer(many=True)}
    )
    def post(self, request, material_id):
        user = request.user  

        # 0. Tekshiruv — user allaqachon javob berganmi?
        already_exists = ReadingUserAnswer.objects.filter(
            user=user,
            reading__reading_material_id=material_id
        ).exists()

        if already_exists:
            return Response(
                {"error": "You have already submitted answers for this material."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 1. Serializer validate
        serializer = ReadingUserAnswerSerializer(
            data=request.data,
            many=True,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # 2. Materialni tekshirish
        try:
            material = ReadingMaterial.objects.get(id=material_id)
        except ReadingMaterial.DoesNotExist:
            return Response(
                {"error": "Reading material not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # 3. Reading_id lar materialga tegishli ekanini tekshirish
        valid_readings = material.reading_materials.values_list("id", flat=True)
        for item in data:
            if item["reading_id"] not in valid_readings:
                return Response(
                    {"error": f"Reading ID {item['reading_id']} does not belong to material {material_id}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # 4. Requestdagi dublikatlarni tekshirish
        seen = set()
        for item in data:
            key = (item["reading_id"], item["question_number"])
            if key in seen:
                return Response(
                    {
                        "error": "Duplicate entries in request",
                        "details": f"Multiple answers for reading_id: {item['reading_id']}, question_number: {item['question_number']}"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            seen.add(key)

        # 5. Javoblarni saqlash (birinchi marta yozilayotganda)
        saved_answers = []
        try:
            with transaction.atomic():
                for item in data:
                    reading = Reading.objects.get(id=item["reading_id"])
                    obj = ReadingUserAnswer.objects.create(
                        user=user,
                        reading=reading,
                        question_number=item["question_number"],
                        answer=item.get("answer")
                    )
                    saved_answers.append(obj)
        except IntegrityError:
            return Response(
                {
                    "error": "Database error",
                    "details": "Something went wrong while saving answers."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # 6. Hisoblash
        all_user_answers_for_material = ReadingUserAnswer.objects.filter(
            user=user,
            reading__reading_material=material
        )

        total_answers = all_user_answers_for_material.count()
        total_correct_answers = all_user_answers_for_material.filter(is_true=True).count()
        total_incorrect_answers = total_answers - total_correct_answers
        percentage_correct = 0
        if total_answers > 0:
            percentage_correct = (total_correct_answers / total_answers) * 100

        overall_reading_score = None
        test_type = material.test_material.test.test_type 
        if test_type == 'mock':
            total_possible_questions = ReadingAnswer.objects.filter(
                reading__reading_material=material
            ).count()

            if total_possible_questions == 40:
                correct_answers_count_for_score = total_correct_answers
                if correct_answers_count_for_score >= 39:
                    overall_reading_score = 9.0
                elif correct_answers_count_for_score >= 37:
                    overall_reading_score = 8.5
                elif correct_answers_count_for_score >= 35:
                    overall_reading_score = 8.0
                elif correct_answers_count_for_score >= 33:
                    overall_reading_score = 7.5
                elif correct_answers_count_for_score >= 30:
                    overall_reading_score = 7.0
                elif correct_answers_count_for_score >= 27:
                    overall_reading_score = 6.5
                elif correct_answers_count_for_score >= 23:
                    overall_reading_score = 6.0
                elif correct_answers_count_for_score >= 19:
                    overall_reading_score = 5.5
                elif correct_answers_count_for_score >= 15:
                    overall_reading_score = 5.0
                elif correct_answers_count_for_score >= 13:
                    overall_reading_score = 4.5
                elif correct_answers_count_for_score >= 10:
                    overall_reading_score = 4.0
                else:
                    overall_reading_score = 0.0
            else:
                overall_reading_score = f"N/A - Total questions for Mock test expected 40, but found {total_possible_questions}"
        
        # 7. Javob qaytarish
        response_serializer = ReadingUserAnswerSerializer(all_user_answers_for_material, many=True)
        response_data = {
            "answers": response_serializer.data,
            "total_answers": total_answers,
            "total_correct_answers": total_correct_answers,
            "total_incorrect_answers": total_incorrect_answers,
            "percentage_correct_for_material": round(percentage_correct, 2),
            "test_type": test_type,
            "overall_score": overall_reading_score,
        }
        return Response(response_data, status=status.HTTP_201_CREATED)

    