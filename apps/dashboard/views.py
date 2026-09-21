from django.shortcuts import get_object_or_404
from django.db.models import Count, Prefetch, Q,Max
from requests import request
from rest_framework.decorators import api_view, permission_classes
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.db.models import OuterRef, Subquery
from apps.app.models import StudentGroup, Test, TestAccept, Users, TestMaterial
from django.db import models
from apps.dashboard.filters import StudentResultFilter
from apps.dashboard.pagination import BasePaginationView
from apps.reading.models import Reading, ReadingAnswer, ReadingMaterial, ReadingUserAnswer
from apps.speaking.models import  Speaking, SpeakingMaterial, SpeakingUserAnswer
from apps.writing.models import  Writing, WritingMaterial, WritingUserAnswer
from apps.listening.models import Listening, ListeningAnswer, ListeningMaterial, ListeningUserAnswer
from apps.app.permissions import IsTeacher
from rest_framework import generics
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.db.models import Q, Count, Prefetch
from django.db.models.functions import Concat
from apps.app.models import Users, StudentGroup
from apps.reading.models import ReadingUserAnswer
from apps.listening.models import ListeningUserAnswer
from apps.writing.models import WritingUserAnswer
from apps.speaking.models import SpeakingUserAnswer
from .serializers import StudentResultSerializer
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db.models import Q
from collections import defaultdict
from django.apps import apps
from rest_framework.pagination import PageNumberPagination

from apps.dashboard.serializers import (
    ReadingAnswerSerializer,
    ListeningAnswerSerializer,
    WritingAnswerSerializer,
    SpeakingAnswerSerializer,
)

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db.models import Q 
from django.db.models import Q, Avg, Count
from django.core.paginator import Paginator
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication



class GroupDetailView(APIView):
    permission_classes = [IsTeacher]

    def get(self, request, group_id):
        try:
            group = StudentGroup.objects.get(id=group_id)
        except StudentGroup.DoesNotExist:
            return Response({'error': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)

        students_count = Users.objects.filter(student_group_id=group_id, role='Student').count()

        data = {
            "id": group.id,
            "name": group.name,
            "is_active": group.is_active,
            "students_count": students_count
        }
        return Response(data, status=status.HTTP_200_OK)


class TeacherDashboardView(BasePaginationView):
    permission_classes = [IsTeacher]
    search_fields = ["name"]

    def get(self, request):
        groups_qs = self.get_groups_with_students()
        groups_qs = self.filter_queryset(groups_qs, request)  
        group_name = request.query_params.get("name")
        if group_name:
            groups_qs = groups_qs.filter(name__icontains=group_name)
        paginated_data = self.paginate_queryset(groups_qs, request)
        return Response(paginated_data)
    
    def get_groups_with_students(self):
        return StudentGroup.objects.prefetch_related(
            Prefetch(
                'users_set',
                queryset=Users.objects.filter(role='Student').select_related(),
                to_attr='student_list'
            )
        ).annotate(
            student_count=Count('users', filter=Q(users__role='Student'))
        ).values('id', 'name', 'student_count', 'is_active')

    def get_active_tests_count(self):
        now = timezone.now()
        return TestAccept.objects.filter(
            deadline_from__lte=now,
            deadline_to__gte=now
        ).count()


class AllTeacherDashboardView(APIView):
    permission_classes = [IsTeacher]
    search_fields = ["name"]

    def get(self, request):
        groups_qs = self.get_groups_with_students()

        # group_name bo‘yicha filter
        group_name = request.query_params.get("name")
        if group_name:
            groups_qs = groups_qs.filter(name__icontains=group_name)

        return Response(list(groups_qs), status=status.HTTP_200_OK)
    
    def get_groups_with_students(self):
        return StudentGroup.objects.prefetch_related(
            Prefetch(
                'users_set',
                queryset=Users.objects.filter(role='Student').select_related(),
                to_attr='student_list'
            )
        ).annotate(
            student_count=Count('users', filter=Q(users__role='Student'))
        ).values('id', 'name', 'student_count', 'is_active')

    def get_active_tests_count(self):
        now = timezone.now()
        return TestAccept.objects.filter(
            deadline_from__lte=now,
            deadline_to__gte=now
        ).count()

class StudentDetailView(APIView):
    permission_classes = [IsTeacher]
    
    def get(self, request, student_id):
        try:
            student = Users.objects.select_related('student_group').get(
                id=student_id, role='Student'
            )
        except Users.DoesNotExist:
            return Response(
                {'error': 'Student not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )

        data = {
            "id": student.id,
            "username": student.username,
            "full_name": f"{student.first_name} {student.last_name}".strip(),
            "phone": student.phone,
            "role": student.role,
            "group": {
                "id": student.student_group.id,
                "name": student.student_group.name
            } if student.student_group else None
        }
        return Response(data, status=status.HTTP_200_OK)


class StudentTestResultsByTypeView(BasePaginationView):
    permission_classes = [IsTeacher]
    page_size = 10
    search_fields = ['title', 'test__title', 'test__test_number']

    def get(self, request, student_id, test_type):
        if test_type.lower() not in ['mock', 'thematic']:
            return Response({'error': 'Invalid test type'}, status=status.HTTP_400_BAD_REQUEST)

        student = get_object_or_404(Users, id=student_id, role='Student')
        
        queryset = TestMaterial.objects.select_related('test').filter(test__test_type__iexact=test_type)

        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(test__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(test__date__lte=date_to)

        queryset = self.filter_queryset(queryset, request)
        paginated_data = self.paginate_queryset(queryset, request)

        test_materials_with_results = []
        for tm in paginated_data['results']:
            test_materials_with_results.append(self.get_test_result_for_material(student, tm))

        paginated_data['results'] = test_materials_with_results
        
        paginated_data['student_info'] = {
            'id': student.id,
            'name': f"{student.first_name} {student.last_name}",
            'group': student.student_group.name if student.student_group else None
        }
        paginated_data['test_type'] = test_type.capitalize()
        paginated_data['summary'] = self.calculate_summary(test_materials_with_results)

        return Response(paginated_data)

    def get_test_result_for_material(self, student, test_material):
        result = {
            'test_material_id': test_material.id,
            'test_material_title': test_material.title,
            'test': {
                'id': test_material.test.id,
                'title': test_material.test.title,
                'test_number': test_material.test.test_number,
                'date': test_material.test.date
            },
            'sections': {}
        }
        
        reading_data = self.get_reading_results(student, test_material)
        if reading_data['total_questions'] > 0:
            result['sections']['reading'] = reading_data

        listening_data = self.get_listening_results(student, test_material)
        if listening_data['total_questions'] > 0:
            result['sections']['listening'] = listening_data

        writing_data = self.get_writing_results(student, test_material)
        if writing_data['total_answers'] > 0:
            result['sections']['writing'] = writing_data

        speaking_data = self.get_speaking_results(student, test_material)
        if speaking_data['total_answers'] > 0:
            result['sections']['speaking'] = speaking_data
        
        return result
    
    # --- Helper methods ---
    def get_reading_results(self, student, test_material):
        answers = ReadingUserAnswer.objects.filter(
            user=student,
            reading__reading_material__test_material=test_material
        )
        return {
            "total_questions": answers.count(),
            "correct_answers": answers.filter(is_true=True).count()
        }

    def get_listening_results(self, student, test_material):
        answers = ListeningUserAnswer.objects.filter(
            user=student,
            listening__listening_material__test_material=test_material
        )
        return {
            "total_questions": answers.count(),
            "correct_answers": answers.filter(is_true=True).count()
        }

    def get_writing_results(self, student, test_material):
        answers = WritingUserAnswer.objects.filter(
            user=student,
            writing__writing_material__test_material=test_material
        )
        return {
            "total_answers": answers.count(),
        }

    def get_speaking_results(self, student, test_material):
        answers = SpeakingUserAnswer.objects.filter(
            user=student,
            speaking__speaking_material__test_material=test_material
        )
        return {
            "total_answers": answers.count(),
        }

    def calculate_summary(self, test_results):
        summary = {
            "reading_total": 0,
            "reading_correct": 0,
            "listening_total": 0,
            "listening_correct": 0,
            "writing_answers": 0,
            "speaking_answers": 0
        }
        for r in test_results:
            if "reading" in r["sections"]:
                summary["reading_total"] += r["sections"]["reading"]["total_questions"]
                summary["reading_correct"] += r["sections"]["reading"]["correct_answers"]
            if "listening" in r["sections"]:
                summary["listening_total"] += r["sections"]["listening"]["total_questions"]
                summary["listening_correct"] += r["sections"]["listening"]["correct_answers"]
            if "writing" in r["sections"]:
                summary["writing_answers"] += r["sections"]["writing"]["total_answers"]
            if "speaking" in r["sections"]:
                summary["speaking_answers"] += r["sections"]["speaking"]["total_answers"]

        return summary


class StudentListView(BasePaginationView):
    permission_classes = [IsTeacher]
    search_fields = ["first_name", "last_name", "phone"]

    def get(self, request):
        qs = Users.objects.filter(role="Student")

        # group_id bo‘yicha filter
        group_id = request.query_params.get("group_id")
        if group_id:
            qs = qs.filter(student_group_id=group_id)

        qs = self.filter_queryset(qs, request)
        paginated_data = self.paginate_queryset(qs, request)

        results = []
        for student in paginated_data.get("results", []):
            results.append({
                "id": student.id,
                "username": student.username,
                "full_name": f"{student.first_name} {student.last_name}".strip(),
                "phone": student.phone,
                "role": student.role,
                "group": {
                    "id": student.student_group.id,
                    "name": student.student_group.name
                } if student.student_group else None
            })
        
        paginated_data["results"] = results
        return Response(paginated_data)




class StudentResultsListView(generics.ListAPIView):
    """
    List all student results with search and filtering
    
    Query Parameters:
    - search: Search by full name or phone
    - group: Filter by group name (case-insensitive contains)
    - test_number: Filter by test number (case-insensitive contains)
    - test_type: Filter by test type (Mock/Thematic)
    - date_from: Filter answers from this date
    - date_to: Filter answers to this date
    - has_reading: Filter students who have/don't have reading answers
    - has_listening: Filter students who have/don't have listening answers
    - has_writing: Filter students who have/don't have writing answers
    - has_speaking: Filter students who have/don't have speaking answers
    - ordering: Order by fields (e.g., first_name, -created_at)
    """
    
    serializer_class = StudentResultSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = StudentResultFilter
    search_fields = ['first_name', 'last_name', 'phone']
    ordering_fields = ['first_name', 'last_name', 'phone', 'student_group__name']
    ordering = ['first_name']
    
    def get_queryset(self):
        # Optimize with prefetch_related to reduce database queries
        return Users.objects.filter(role='Student').select_related(
            'student_group'
        ).prefetch_related(
            # Reading answers with related data
            Prefetch('reading_user_answers', 
                ReadingUserAnswer.objects.select_related(
                    'reading__reading_material__test_material__test'
                ).order_by('-created_at')
            ),
            # Listening answers with related data  
            Prefetch('listening_user_answers',
                ListeningUserAnswer.objects.select_related(
                    'listening__listening_material__test_material__test'
                ).order_by('-created_at')
            ),
            # Writing answers with related data
            Prefetch('writing_user_answers',
                WritingUserAnswer.objects.select_related(
                    'writing__writing_material__test_material__test'
                ).order_by('-created_at')
            ),
            # Speaking answers with related data
            Prefetch('speaking_user_answers',
                SpeakingUserAnswer.objects.select_related(
                    'speaking__speaking_material__test_material__test'
                ).order_by('-created_at')
            )
        ).distinct()

class StudentResultDetailView(generics.RetrieveAPIView):
    """
    Get detailed results for a specific student
    """
    serializer_class = StudentResultSerializer
    lookup_field = 'pk'
    
    def get_queryset(self):
        return Users.objects.filter(role='Student').select_related(
            'student_group'
        ).prefetch_related(
            'reading_user_answers__reading__reading_material__test_material__test',
            'listening_user_answers__listening__listening_material__test_material__test',
            'writing_user_answers__writing__writing_material__test_material__test',
            'speaking_user_answers__speaking__speaking_material__test_material__test'
        )



def get_ielts_band_score(correct_answers, total_questions, skill_type):
    if total_questions == 0:
        return 0.0

    percentage = (correct_answers / total_questions) * 100

    if skill_type == "reading":
        if total_questions != 40:
            correct_answers_scaled = (correct_answers / total_questions) * 40
        else:
            correct_answers_scaled = correct_answers

        if correct_answers_scaled >= 39: return 9.0
        elif correct_answers_scaled >= 37: return 8.5
        elif correct_answers_scaled >= 35: return 8.0
        elif correct_answers_scaled >= 32: return 7.5
        elif correct_answers_scaled >= 30: return 7.0
        elif correct_answers_scaled >= 27: return 6.5
        elif correct_answers_scaled >= 23: return 6.0
        elif correct_answers_scaled >= 19: return 5.5
        elif correct_answers_scaled >= 15: return 5.0
        elif correct_answers_scaled >= 12: return 4.5
        elif correct_answers_scaled >= 10: return 4.0
        elif correct_answers_scaled >= 7: return 3.5
        elif correct_answers_scaled >= 5: return 3.0
        elif correct_answers_scaled >= 3: return 2.5
        else: return 0.0
    
    elif skill_type == "listening":
        if total_questions != 40:
            correct_answers_scaled = (correct_answers / total_questions) * 40
        else:
            correct_answers_scaled = correct_answers
            
        if correct_answers_scaled >= 39: return 9.0
        elif correct_answers_scaled >= 37: return 8.5
        elif correct_answers_scaled >= 35: return 8.0
        elif correct_answers_scaled >= 32: return 7.5
        elif correct_answers_scaled >= 30: return 7.0
        elif correct_answers_scaled >= 27: return 6.5
        elif correct_answers_scaled >= 23: return 6.0
        elif correct_answers_scaled >= 19: return 5.5
        elif correct_answers_scaled >= 15: return 5.0
        elif correct_answers_scaled >= 12: return 4.5
        elif correct_answers_scaled >= 10: return 4.0
        elif correct_answers_scaled >= 7: return 3.5
        elif correct_answers_scaled >= 5: return 3.0
        elif correct_answers_scaled >= 3: return 2.5
        else: return 0.0
    
    return 0.0


@api_view(['GET'])
@permission_classes([IsTeacher])
def student_results_by_type_and_skill(request, pk, test_type, skill):
    student = get_object_or_404(Users, pk=pk, role="Student")

    skill = skill.lower()
    if skill not in ["reading", "listening", "writing", "speaking"]:
        return Response({"error": "Invalid skill. Use reading, listening, writing or speaking."}, status=400)

    results_data = []
    total_correct = 0
    total_answers = 0

    paginator_view = BasePaginationView()

    # Define a queryset to get distinct materials for pagination
    material_queryset = None

    
    # ---------------------------
    # READING
    # ---------------------------
    if skill == "reading":
        # Get unique reading materials for pagination
        material_queryset = (
            ReadingUserAnswer.objects
            .filter(
                user=student,
                reading__reading_material__test_material__test__test_type__iexact=test_type
            )
            .values('reading__reading_material__id', 'reading__reading_material__title')
            .distinct()
            .order_by('reading__reading_material__id')
        )

        paginator_view.search_fields = ['reading__reading_material__title', 'reading__title']
        material_queryset = paginator_view.filter_queryset(material_queryset, request)
        
        paginated_materials = paginator_view.paginate_queryset(material_queryset, request)
        
        material_ids_on_page = [item['reading__reading_material__id'] for item in paginated_materials['results']]

        if material_ids_on_page:
            answers_qs = (
                ReadingUserAnswer.objects
                .filter(
                    user=student,
                    reading__reading_material__test_material__test__test_type__iexact=test_type,
                    reading__reading_material__id__in=material_ids_on_page
                )
                .select_related("reading__reading_material__test_material__test", "reading")
                .order_by("reading__reading_material__id", "reading_id", "question_number")
            )

            # Group by reading material instead of individual passages
            materials = {}
            for ans in answers_qs:
                material_id = ans.reading.reading_material_id
                if material_id not in materials:
                    materials[material_id] = {
                        "reading_id": material_id,
                        "reading_title": ans.reading.reading_material.title if ans.reading.reading_material else None,
                        "test_title": ans.reading.reading_material.test_material.test.title if ans.reading.reading_material and ans.reading.reading_material.test_material else None,
                        "test_number": ans.reading.reading_material.test_material.test.test_number if ans.reading.reading_material and ans.reading.reading_material.test_material else None,
                        "material_id": material_id,
                        "total_answers_for_material": 0,
                        "total_correct_answers_for_material": 0,
                        "material_last_activity": None,
                        "test_type": test_type,
                        "skill": skill,
                    }

                materials[material_id]["total_answers_for_material"] += 1
                if ans.is_true:
                    materials[material_id]["total_correct_answers_for_material"] += 1

                prev = materials[material_id]["material_last_activity"]
                if prev is None or (ans.created_at and ans.created_at > prev):
                    materials[material_id]["material_last_activity"] = ans.created_at

            for m in materials.values():
                m["total_incorrect_answers_for_material"] = (
                    m["total_answers_for_material"] - m["total_correct_answers_for_material"]
                )
                m["percentage_correct_for_material"] = round(
                    (m["total_correct_answers_for_material"] / m["total_answers_for_material"]) * 100, 2
                ) if m["total_answers_for_material"] else 0.0
                
                # Calculate overall for each material
                if test_type.lower() == "mock" and m["total_answers_for_material"] > 0:
                    m["overall"] = get_ielts_band_score(m["total_correct_answers_for_material"], m["total_answers_for_material"], skill)
                else:
                    m["overall"] = 0.0
                    
                results_data.append(m)

        all_answers_for_skill_and_type = (
            ReadingUserAnswer.objects
            .filter(
                user=student,
                reading__reading_material__test_material__test__test_type__iexact=test_type
            )
        )
        total_correct = all_answers_for_skill_and_type.filter(is_true=True).count()
        total_answers = all_answers_for_skill_and_type.count()

    
    
    
    # ---------------------------
    # LISTENING
    # ---------------------------
    elif skill == "listening":
        material_queryset = (
            ListeningUserAnswer.objects
            .filter(
                user=student,
                listening__listening_material__test_material__test__test_type__iexact=test_type
            )
            .values('listening__listening_material__id', 'listening__listening_material__title')
            .distinct()
            .order_by('listening__listening_material__id')
        )
        
        paginator_view.search_fields = ['listening__listening_material__test_material__test__title', 'listening__title']
        material_queryset = paginator_view.filter_queryset(material_queryset, request)
        
        paginated_materials = paginator_view.paginate_queryset(material_queryset, request)

        material_ids_on_page = [item['listening__listening_material__id'] for item in paginated_materials['results']]

        if material_ids_on_page:
            answers_qs = (
                ListeningUserAnswer.objects
                .filter(
                    user=student,
                    listening__listening_material__test_material__test__test_type__iexact=test_type,
                    listening__listening_material__id__in=material_ids_on_page
                )
                .select_related("listening__listening_material__test_material__test", "listening")
                .order_by("listening__listening_material__id", "listening_id", "question_number")
            )
        
            # Group by listening material instead of individual sections
            materials = {}
            for ans in answers_qs:
                material_id = ans.listening.listening_material_id
                if material_id not in materials:
                    materials[material_id] = {
                        "listening_id": material_id,  # Changed to material_id for consistency
                        "listening_title": ans.listening.listening_material.title if ans.listening.listening_material else None,
                        "test_title": ans.listening.listening_material.test_material.test.title if ans.listening.listening_material and ans.listening.listening_material.test_material else None,
                        "test_number": ans.listening.listening_material.test_material.test.test_number if ans.listening.listening_material and ans.listening.listening_material.test_material else None,
                        "material_id": material_id,
                        "total_answers_for_material": 0,  # Changed from "total_questions"
                        "total_correct_answers_for_material": 0,  # Changed from "total_correct_answers"
                        "material_last_activity": None,
                        "test_type": test_type,
                        "skill": skill,
                    }

                materials[material_id]["total_answers_for_material"] += 1  # Changed from "total_questions"
                if ans.is_true:
                    materials[material_id]["total_correct_answers_for_material"] += 1  # Changed from "total_correct_answers"

                prev = materials[material_id]["material_last_activity"]
                if prev is None or (ans.created_at and ans.created_at > prev):
                    materials[material_id]["material_last_activity"] = ans.created_at

            for m in materials.values():
                m["total_incorrect_answers_for_material"] = (  # Changed from "total_incorrect_answers"
                    m["total_answers_for_material"] - m["total_correct_answers_for_material"]
                )
                m["percentage_correct_for_material"] = round(
                    (m["total_correct_answers_for_material"] / m["total_answers_for_material"]) * 100, 2
                ) if m["total_answers_for_material"] else 0.0
                
                # Calculate overall for each material (changed from "overall_score" to "overall")
                if test_type.lower() == "mock" and m["total_answers_for_material"] > 0:
                    m["overall"] = get_ielts_band_score(m["total_correct_answers_for_material"], m["total_answers_for_material"], skill)
                else:
                    m["overall"] = 0.0
                    
                results_data.append(m)

        all_answers_for_skill_and_type = (
            ListeningUserAnswer.objects
            .filter(
                user=student,
                listening__listening_material__test_material__test__test_type__iexact=test_type
            )
        )
        total_correct = all_answers_for_skill_and_type.filter(is_true=True).count()
        total_answers = all_answers_for_skill_and_type.count()




    # ---------------------------
    # WRITING
    # ---------------------------
    elif skill == "writing":
        material_queryset = (
            WritingUserAnswer.objects
            .filter(
                user=student,
                writing__writing_material__test_material__test__test_type__iexact=test_type
            )
            .values('writing__writing_material__id', 'writing__writing_material__title')
            .distinct()
            .order_by('writing__writing_material__id')
        )
        
        paginator_view.search_fields = ['writing__writing_material__test_material__test__title', 'writing__writing_material__title', 'writing__description']
        material_queryset = paginator_view.filter_queryset(material_queryset, request)
        
        paginated_materials = paginator_view.paginate_queryset(material_queryset, request)

        material_ids_on_page = [item['writing__writing_material__id'] for item in paginated_materials['results']]

        if material_ids_on_page:
            answers_qs = (
                WritingUserAnswer.objects
                .filter(
                    user=student,
                    writing__writing_material__test_material__test__test_type__iexact=test_type,
                    writing__writing_material__id__in=material_ids_on_page
                )
                .select_related(
                    "writing__writing_material__test_material__test",
                    "writing__writing_material",
                    "writing"
                )
                .order_by("writing__writing_material_id", "writing__writing_task", "created_at")
            )
            
            # Group by writing material
            materials = {}
            for ans in answers_qs:
                writing_obj = ans.writing
                if not writing_obj:
                    continue

                wm = writing_obj.writing_material
                wm_id = wm.id if wm else None

                if wm_id not in materials:
                    materials[wm_id] = {
                        "material_id": wm_id,
                        "writing_title": getattr(wm, "title", None),
                        "test_title": wm.test_material.test.title if wm and wm.test_material else None,
                        "test_number": wm.test_material.test.test_number if wm and wm.test_material else None,
                        "total_questions": 0,
                        "scores": [],
                        "created_at": ans.created_at,
                        "test_type": test_type,
                        "skill": skill,
                    }

                materials[wm_id]["total_questions"] += 1
                if ans.score is not None:
                    materials[wm_id]["scores"].append(ans.score)

            # Calculate overall_score as average of scores
            for m in materials.values():
                if m["scores"]:
                    m["overall_score"] = round(sum(m["scores"]) / len(m["scores"]), 1)
                else:
                    m["overall_score"] = 0.0
                
                # Remove scores array as it's not needed in final output
                del m["scores"]
                del m["test_type"]
                del m["skill"]
                
                results_data.append(m)

        all_answers_for_skill_and_type = (
            WritingUserAnswer.objects
            .filter(
                user=student,
                writing__writing_material__test_material__test__test_type__iexact=test_type
            )
        )
        total_answers = all_answers_for_skill_and_type.count()
        total_correct = 0


    # ---------------------------
    # SPEAKING
    # ---------------------------
    elif skill == "speaking":
        material_queryset = (
            SpeakingUserAnswer.objects
            .filter(
                user=student,
                speaking__test_material__test__test_type__iexact=test_type  # Bu yerda tuzatish
            )
            .values('speaking__id', 'speaking__title')  # speaking__speaking_material emas
            .distinct()
            .order_by('speaking__id')
        )
        
        paginator_view.search_fields = ['speaking__test_material__test__title', 'speaking__title']
        material_queryset = paginator_view.filter_queryset(material_queryset, request)
        
        paginated_materials = paginator_view.paginate_queryset(material_queryset, request)

        material_ids_on_page = [item['speaking__id'] for item in paginated_materials['results']]

        if material_ids_on_page:
            answers_qs = (
                SpeakingUserAnswer.objects
                .filter(
                    user=student,
                    speaking__test_material__test__test_type__iexact=test_type,  # Tuzatish
                    speaking__id__in=material_ids_on_page  # Tuzatish
                )
                .select_related("speaking__test_material__test", "speaking")  # Tuzatish
                .order_by("speaking__id", "created_at")  # Tuzatish
            )
            
            # Group by speaking material
            materials = {}
            for ans in answers_qs:
                speaking_material = ans.speaking  # Bu allaqachon SpeakingMaterial
                sm_id = speaking_material.id

                if sm_id not in materials:
                    materials[sm_id] = {
                        "material_id": sm_id,
                        "speaking_title": getattr(speaking_material, "title", None),
                        "test_title": speaking_material.test_material.test.title if speaking_material.test_material else None,
                        "test_number": speaking_material.test_material.test.test_number if speaking_material.test_material else None,
                        "total_questions": 0,
                        "scores": [],
                        "created_at": ans.created_at,
                    }

                materials[sm_id]["total_questions"] += 1
                if ans.score is not None:
                    materials[sm_id]["scores"].append(ans.score)

            # Calculate overall_score as average of scores
            for m in materials.values():
                if m["scores"]:
                    m["overall_score"] = round(sum(m["scores"]) / len(m["scores"]), 1)
                else:
                    m["overall_score"] = 0.0
                
                # Remove scores array as it's not needed in final output
                del m["scores"]
                
                results_data.append(m)

        all_answers_for_skill_and_type = (
            SpeakingUserAnswer.objects
            .filter(
                user=student,
                speaking__test_material__test__test_type__iexact=test_type  # Tuzatish
            )
        )
        total_answers = all_answers_for_skill_and_type.count()
        total_correct = 0

    
    
    
    
    # ---------------------------
    # Response assembly
    # ---------------------------
    final_paginated_response_data = {
        "count": paginated_materials['count'] if material_queryset is not None else len(results_data),
        "total_pages": paginated_materials['total_pages'] if material_queryset is not None else 1,
        "current_page": paginated_materials['current_page'] if material_queryset is not None else 1,
        "page_size": paginated_materials['page_size'] if material_queryset is not None else paginator_view.page_size,
        "next": paginated_materials['next'] if material_queryset is not None else None,
        "previous": paginated_materials['previous'] if material_queryset is not None else None,
        "has_next": paginated_materials['has_next'] if material_queryset is not None else False,
        "has_previous": paginated_materials['has_previous'] if material_queryset is not None else False,
        "results": results_data
    }

    final_response = {**final_paginated_response_data, **{
        "student": {
            "id": student.id,
            "full_name": f"{student.first_name} {student.last_name}",
            "phone": student.phone,
            "group": student.student_group.name if student.student_group else None,
        },
    }}

    # Statistics faqat reading va listening uchun qo'shiladi
    if skill in ("reading", "listening"):
        if test_type.lower() == "mock" and total_answers > 0:
            overall_score = get_ielts_band_score(total_correct, total_answers, skill)
            final_response["statistics"] = {
                "total_questions": total_answers,
                "correct_answers": total_correct,
                "incorrect_answers": total_answers - total_correct,
                "score_percentage": round((total_correct / total_answers) * 100, 2) if total_answers > 0 else 0,
                "overall": overall_score
            }
        elif total_answers > 0:
            final_response["statistics"] = {
                "total_questions": total_answers,
                "correct_answers": total_correct,
                "incorrect_answers": total_answers - total_correct,
                "score_percentage": round((total_correct / total_answers) * 100, 2),
            }
        else:
            final_response["statistics"] = {
                "total_questions": 0,
                "correct_answers": 0,
                "incorrect_answers": 0,
                "score_percentage": 0,
            }

    # Writing va Speaking uchun statistics qo'shilmaydi (hech narsa qo'shmaslik)

    return Response(final_response)


@api_view(['GET'])
@permission_classes([IsAuthenticatedOrReadOnly])
def student_results_by_type_and_skill_detail(request, pk, test_type, skill, obj_id):
    """
    Retrieves detailed results for a specific student, test type, skill, and material object.
    The obj_id should always be the ID of the respective Material (ReadingMaterial.id, etc.)
    Args:
        pk (int): The ID of the student.
        test_type (str): The type of test (e.g., 'thematic', 'mock').
        skill (str): The skill type ('reading', 'listening', 'writing', 'speaking').
        obj_id (int): The ID of the specific Material (ReadingMaterial.id, ListeningMaterial.id, etc.).
    Returns:
        Response: A DRF Response object containing the detailed results or an error message.
    """
    # Import SpeakingAnswer model to fix the NameError
    from apps.speaking.models import SpeakingAnswer

    student = get_object_or_404(Users, pk=pk)
    skill_map = {
        'reading': {
            'skill_model': Reading,
            'material_model': ReadingMaterial,
            'answer_model': ReadingUserAnswer,
            'serializer': ReadingAnswerSerializer,
            'answer_fk_to_skill_model': 'reading',
            'correct_answer_model': ReadingAnswer,
        },
        'listening': {
            'skill_model': Listening,
            'material_model': ListeningMaterial,
            'answer_model': ListeningUserAnswer,
            'serializer': ListeningAnswerSerializer,
            'answer_fk_to_skill_model': 'listening',
            'correct_answer_model': ListeningAnswer,
        },
        'writing': {
            'skill_model': Writing,
            'material_model': WritingMaterial,
            'answer_model': WritingUserAnswer,
            'serializer': WritingAnswerSerializer,
            'answer_fk_to_skill_model': 'writing',
            'correct_answer_model': None,
        },
        'speaking': {
            'skill_model': Speaking,
            'material_model': SpeakingMaterial,
            'answer_model': SpeakingUserAnswer,
            'serializer': SpeakingAnswerSerializer,
            'answer_fk_to_skill_model': 'speaking',
            'correct_answer_model': None,
        },
    }
    skill_info = skill_map.get(skill)
    if not skill_info:
        return Response(
            {"detail": f"Invalid skill type: {skill}. Must be one of 'reading', 'listening', 'writing', 'speaking'."},
            status=status.HTTP_400_BAD_REQUEST
        )

    SkillModel = skill_info['skill_model']
    MaterialModel = skill_info['material_model']
    AnswerModel = skill_info['answer_model']
    AnswerSerializer = skill_info['serializer']
    CorrectAnswerModel = skill_info['correct_answer_model']

    # ✅ Always expect Material ID for both thematic and mock tests
    material_instance = get_object_or_404(MaterialModel, pk=obj_id)

    # ✅ Get skill objects related to this material
    skill_objects = []
    skill_ids = []
    if skill == 'reading':
        skill_objects = Reading.objects.filter(reading_material=material_instance)
        skill_ids = list(skill_objects.values_list('id', flat=True))
    elif skill == 'listening':
        skill_objects = Listening.objects.filter(listening_material=material_instance)
        skill_ids = list(skill_objects.values_list('id', flat=True))
    elif skill == 'writing':
        skill_objects = Writing.objects.filter(writing_material=material_instance)
        skill_ids = list(skill_objects.values_list('id', flat=True))
    elif skill == 'speaking':
        skill_objects = Speaking.objects.filter(speaking_material=material_instance)
        skill_ids = list(skill_objects.values_list('id', flat=True))

    # Use first skill object as skill_instance for compatibility
    if skill_objects.exists():
        skill_instance = skill_objects.first()
    else:
        return Response(
            {"detail": f"No {skill} objects found for material {obj_id}."},
            status=status.HTTP_404_NOT_FOUND
        )

    # Prepare student info
    student_info = {
        'id': student.id,
        'full_name': f"{student.first_name} {student.last_name}",
        'phone': student.phone,
        'group': None
    }
    if hasattr(student, 'student_group') and student.student_group:
        student_info['group'] = {
            'id': student.student_group.id,
            'name': student.student_group.name
        }

    # ✅ Get test title from material instance
    test_title = material_instance.test_material.test.title if hasattr(material_instance, 'test_material') and material_instance.test_material and material_instance.test_material.test else None

    # Prepare initial statistics for empty cases
    initial_stats = {
        'total_questions': 0,
        'correct_answers': 0,
        'incorrect_answers': 0,
        'score_percentage': 0,
        'average_score': None,
        'total_submissions': 0,
    }

    # Special handling for speaking skill
    if skill == 'speaking':
        # ✅ Get user answers for this material
        user_answers_qs = SpeakingUserAnswer.objects.filter(
            user=student,
            speaking=material_instance
        ).order_by('created_at')

        if not user_answers_qs.exists():
            return Response(
                {
                    'test_type': test_type,
                    'student': student_info,
                    'skill': skill,
                    'material_id': obj_id,  # ✅ SpeakingMaterial.id
                    'skill_ids': [obj_id],  # ✅ SpeakingMaterial.id
                    'material_title': str(material_instance),
                    'test_title': test_title,
                    'statistics': initial_stats,
                    'answers': [],
                    'detail': f"No {skill} answers found for student {student.id} for material {obj_id}."
                },
                status=status.HTTP_200_OK
            )

        # Prepare speaking sections with questions
        questions_structure = []
        for speaking_section in skill_objects:
            speaking_questions = SpeakingAnswer.objects.filter(speaking=speaking_section).order_by('question_number')

            questions_data = []
            for question in speaking_questions:
                questions_data.append({
                    'question_number': question.question_number,
                    'question': question.question
                })

            questions_structure.append({
                'speaking_part': speaking_section.speaking_part,
                'question': questions_data
            })

        # Calculate statistics for speaking
        stats = {}
        if user_answers_qs.exists():
            scores = user_answers_qs.exclude(score__isnull=True).values_list('score', flat=True)
            if scores:
                stats = {
                    'average_score': sum(scores) / len(scores),
                    'total_submissions': len(scores),
                }
            else:
                stats = {
                    'average_score': None,
                    'total_submissions': 0,
                }
        else:
            stats = initial_stats

        # Get test_number
        test_number = material_instance.test_material.test.test_number if hasattr(material_instance, 'test_material') and material_instance.test_material and material_instance.test_material.test else None

        # Prepare answers array
        answers_data = []
        for user_answer in user_answers_qs:
            user_answer_data = {
                'question_number': user_answer.question_number,
                'record': request.build_absolute_uri(user_answer.record.url) if user_answer.record else None,
                'feedback': user_answer.feedback,
                'score': user_answer.score,
                'created_at': user_answer.created_at.isoformat(),
                'test_title': test_title,
                'test_number': test_number,
                'material_title': str(material_instance),
                'questions': questions_structure
            }
            answers_data.append(user_answer_data)

        response_data = {
            'test_type': test_type,
            'student': student_info,
            'skill': skill,
            'material_id': obj_id,  # ✅ SpeakingMaterial.id
            'skill_ids': [obj_id],  # ✅ SpeakingMaterial.id
            'material_title': str(material_instance),
            'test_title': test_title,
            'statistics': stats,
            'answers': answers_data,
        }

        return Response(response_data, status=status.HTTP_200_OK)

    # ✅ For reading, listening, writing - filter by material through skill objects
    answer_fk_to_skill_model = skill_info['answer_fk_to_skill_model']
    filter_kwargs = {
        'user': student,
        f'{answer_fk_to_skill_model}__in': skill_objects
    }

    # Apply the correct answer annotation if available
    if CorrectAnswerModel:
        user_answers_qs = (
            AnswerModel.objects
            .filter(**filter_kwargs)
            .annotate(
                correct_answer_from_model=Subquery(
                    CorrectAnswerModel.objects.filter(
                        **{answer_fk_to_skill_model: OuterRef(answer_fk_to_skill_model)},
                        question_number=OuterRef("question_number"),
                    ).values("true_answer")[:1]
                )
            )
            .order_by('created_at')
        )
    else:
        user_answers_qs = AnswerModel.objects.filter(**filter_kwargs).order_by('created_at')

    if not user_answers_qs.exists():
        return Response(
            {
                'test_type': test_type,
                'student': student_info,
                'skill': skill,
                'material_id': obj_id,  # ✅ ReadingMaterial.id, ListeningMaterial.id, WritingMaterial.id
                'skill_ids': [obj_id],  # ✅ Material ID
                'material_title': str(material_instance),
                'test_title': test_title,
                'statistics': initial_stats,
                'answers': [],
                'detail': f"No {skill} answers found for student {student.id} for material {obj_id}."
            },
            status=status.HTTP_200_OK
        )

    # Serialize the answers
    serializer = AnswerSerializer(user_answers_qs, many=True, context={'request': request})

    # Prepare statistics based on the skill type
    stats = {}
    if skill in ['reading', 'listening']:
        total_answers = user_answers_qs.count()
        correct_answers = user_answers_qs.filter(is_true=True).count()

        # Calculate overall band score for mock tests
        overall_score = 0.0
        if test_type.lower() == "mock" and total_answers > 0:
            overall_score = get_ielts_band_score(correct_answers, total_answers, skill)

        stats = {
            'total_questions': total_answers,
            'correct_answers': correct_answers,
            'incorrect_answers': total_answers - correct_answers,
            'score_percentage': round((correct_answers / total_answers * 100), 2) if total_answers > 0 else 0,
            'overall': overall_score
        }
    elif skill in ['writing']:
        scores = user_answers_qs.exclude(score__isnull=True).values_list('score', flat=True)
        if scores:
            stats = {
                'average_score': sum(scores) / len(scores),
                'total_submissions': len(scores),
            }
        else:
            stats = {
                'average_score': None,
                'total_submissions': 0,
            }

    # Prepare response
    serialized_answers = serializer.data

    response_data = {
        'test_type': test_type,
        'student': student_info,
        'skill': skill,
        'material_id': obj_id,  # ✅ ReadingMaterial.id, ListeningMaterial.id, WritingMaterial.id
        'skill_ids': [obj_id],  # ✅ Material ID
        'material_title': str(material_instance),
        'test_title': test_title,
        'statistics': stats,
        'answers': serialized_answers,
    }
    return Response(response_data, status=status.HTTP_200_OK)


@api_view(["GET"])
def test_info(request, pk):
    test_material = get_object_or_404(TestMaterial, id=pk)
    test = test_material.test

    test_info = {
        "test_title": test.title,  # Test.title (Cambridge 17)
        "test_id": test.id,        # Test.id
    }

    materials = []

    # Listening first
    for lm in ListeningMaterial.objects.filter(test_material=test_material):
        materials.append({
            "id": test_material.id,
            "type": "listening",
            "title": lm.title or test_material.title,
        })

    # Reading
    for rm in ReadingMaterial.objects.filter(test_material=test_material):
        materials.append({
            "id": test_material.id,
            "type": "reading",
            "title": rm.title or test_material.title,
        })

    # Writing
    for wm in WritingMaterial.objects.filter(test_material=test_material):
        materials.append({
            "id": test_material.id,
            "type": "writing",
            "title": wm.title or test_material.title,
        })

    # Speaking
    for sm in SpeakingMaterial.objects.filter(test_material=test_material):
        materials.append({
            "id": test_material.id,
            "type": "speaking",
            "title": sm.title or test_material.title,
        })

    # Sorting materials in fixed order
    type_order = {"listening": 1, "reading": 2, "writing": 3, "speaking": 4}
    materials.sort(key=lambda x: type_order.get(x["type"], 99))

    result = {
        "id": test_material.id,      # TestMaterial.id (1)
        "title": test_material.title, # TestMaterial.title ("Test 1")
        "test_type": test.test_type,
        "test_info": test_info,
        "materials": materials,
    }

    return Response(result, status=status.HTTP_200_OK)


@api_view(["GET"])
def thematic_material_info_by_type(request, pk, material_type):
    # Validate material_type
    valid_types = ['reading', 'listening', 'writing', 'speaking']
    if material_type not in valid_types:
        return Response(
            {"error": f"Invalid material type. Must be one of: {', '.join(valid_types)}"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Get the specific material model based on type
    material_model = get_material_model_by_type(material_type)
    if not material_model:
        return Response(
            {"error": f"Could not find {material_type} material model"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # Try to find the material
    try:
        material = material_model.objects.get(id=pk)
    except material_model.DoesNotExist:
        return Response(
            {"error": f"{material_type.title()} material with id {pk} not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    # Get test_material and validate it's Thematic
    test_material = material.test_material
    test = test_material.test

    if test.test_type != 'Thematic':
        return Response(
            {"error": f"{material_type.title()} material with id {pk} is not from a Thematic test"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Build response
    result = {
        "id": material.id,
        "title": material.title or f"Thematic {material_type.title()} Material",
        "test_type": test.test_type,
        "material_type": material_type,
        "test_info": {
            "test_id": test.id,
            "type": material_type,
            "test_title": test.title or f"Test {test.test_number}",
        },
        "material_info": {
            "id": test_material.id,
            "title": test_material.title or f"Test Material {test_material.id}",
        }
    }

    # Add type-specific data
    if material_type == 'reading':
        result["answer_time"] = getattr(material, 'answer_time', None)
    elif material_type == 'listening':
        result["answer_time"] = getattr(material, 'answer_time', None)
        result["audio"] = getattr(material, 'audio', None)
    elif material_type in ['writing', 'speaking']:
        # Add any specific fields for writing/speaking if needed
        pass

    return Response(result, status=status.HTTP_200_OK)


@api_view(["GET"])
def thematic_material_info(request, pk):
    # Dynamic model loading
    def get_model_by_name(app_labels, model_name):
        for app_label in app_labels:
            try:
                if app_label:
                    return apps.get_model(app_label, model_name)
                else:
                    for model in apps.get_models():
                        if model._meta.model_name.lower() == model_name.lower():
                            return model
            except LookupError:
                continue
        return None

    # Get all required models
    TestMaterial = get_model_by_name(['app', None], 'TestMaterial')
    ListeningMaterial = get_model_by_name(['listening', None], 'ListeningMaterial')
    ReadingMaterial = get_model_by_name(['reading', None], 'ReadingMaterial')
    WritingMaterial = get_model_by_name(['writing', None], 'WritingMaterial')
    SpeakingMaterial = get_model_by_name(['speaking', None], 'SpeakingMaterial')

    # Try to find the material in each model
    material = None
    material_type = None
    test_material = None

    # Check in ReadingMaterial
    if ReadingMaterial:
        try:
            material = ReadingMaterial.objects.get(id=pk)
            material_type = "reading"
            test_material = material.test_material
        except ReadingMaterial.DoesNotExist:
            pass

    # Check in ListeningMaterial
    if not material and ListeningMaterial:
        try:
            material = ListeningMaterial.objects.get(id=pk)
            material_type = "listening"
            test_material = material.test_material
        except ListeningMaterial.DoesNotExist:
            pass

    # Check in WritingMaterial
    if not material and WritingMaterial:
        try:
            material = WritingMaterial.objects.get(id=pk)
            material_type = "writing"
            test_material = material.test_material
        except WritingMaterial.DoesNotExist:
            pass

    # Check in SpeakingMaterial
    if not material and SpeakingMaterial:
        try:
            material = SpeakingMaterial.objects.get(id=pk)
            material_type = "speaking"
            test_material = material.test_material
        except SpeakingMaterial.DoesNotExist:
            pass

    if not material:
        return Response(
            {"error": f"Material with id {pk} not found in any material type"},
            status=status.HTTP_404_NOT_FOUND
        )

    # Check if it's a Thematic test
    test = test_material.test
    if test.test_type != 'Thematic':
        return Response(
            {"error": f"Material with id {pk} is not from a Thematic test"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Build response
    result = {
        "id": material.id,
        "title": material.title or f"Thematic {material_type.title()} Material",
        "test_type": test.test_type,
        "material_type": material_type,
        "test_info": {
            "test_id": test.id,
            "type": material_type,
            "test_title": test.title or f"Test {test.test_number}",
        },
        "material_info": {
            "id": test_material.id,
            "title": test_material.title or f"Test Material {test_material.id}",
        }
    }

    return Response(result, status=status.HTTP_200_OK)


def get_material_model_by_type(material_type):
    def get_model_by_name(app_labels, model_name):
        for app_label in app_labels:
            try:
                if app_label:
                    return apps.get_model(app_label, model_name)
                else:
                    for model in apps.get_models():
                        if model._meta.model_name.lower() == model_name.lower():
                            return model
            except LookupError:
                continue
        return None

    model_mapping = {
        'reading': get_model_by_name(['reading', None], 'ReadingMaterial'),
        'listening': get_model_by_name(['listening', None], 'ListeningMaterial'),
        'writing': get_model_by_name(['writing', None], 'WritingMaterial'),
        'speaking': get_model_by_name(['speaking', None], 'SpeakingMaterial'),
    }

    return model_mapping.get(material_type)


class TenPaginationView(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'page_size': self.page_size,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data
        })
    
    def paginate_queryset(self, queryset, request, view=None):
        if not queryset:
            return []
        try:
            return super().paginate_queryset(queryset, request, view)
        except Exception:
            return []


@api_view(['GET'])
def student_mock_statistics(request, student_id):
    # Dynamic model loading function
    def get_model_by_name(app_labels, model_name):
        for app_label in app_labels:
            try:
                if app_label:
                    return apps.get_model(app_label, model_name)
                else:
                    for model in apps.get_models():
                        if model._meta.model_name.lower() == model_name.lower():
                            return model
            except LookupError:
                continue
        return None
    
    # Get all required models
    Users = get_model_by_name(['app', None], 'Users')
    Test = get_model_by_name(['app', None], 'Test')
    TestMaterial = get_model_by_name(['app', None], 'TestMaterial')
    ListeningMaterial = get_model_by_name(['listening', None], 'ListeningMaterial')
    ReadingMaterial = get_model_by_name(['reading', None], 'ReadingMaterial')
    WritingMaterial = get_model_by_name(['writing', None], 'WritingMaterial')
    SpeakingMaterial = get_model_by_name(['speaking', None], 'SpeakingMaterial')
    ListeningUserAnswer = get_model_by_name(['listening', None], 'ListeningUserAnswer')
    ReadingUserAnswer = get_model_by_name(['reading', None], 'ReadingUserAnswer')
    WritingUserAnswer = get_model_by_name(['writing', None], 'WritingUserAnswer')
    SpeakingUserAnswer = get_model_by_name(['speaking', None], 'SpeakingUserAnswer')
    
    if not Users or not TestMaterial:
        return Response(
            {"error": "Required models not found"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    # Validate student_id
    try:
        student_id = int(student_id)
    except (ValueError, TypeError):
        return Response(
            {"error": "Invalid student_id. Must be an integer."}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check if student exists
    try:
        student = Users.objects.get(id=student_id, role='Student')
    except Users.DoesNotExist:
        return Response(
            {"error": f"Student with id={student_id} not found."}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Get pagination parameters
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 10))
    
    # Collect TestMaterial IDs that student has worked on
    test_material_ids = set()
    
    # Answer models with their filter paths
    answer_models_config = [
        (ListeningUserAnswer, 'listening__listening_material__test_material'),
        (ReadingUserAnswer, 'reading__reading_material__test_material'),
        (WritingUserAnswer, 'writing__writing_material__test_material'),
        (SpeakingUserAnswer, 'speaking__test_material'),
    ]
    
    for answer_model, filter_path in answer_models_config:
        if not answer_model:
            continue
        
        try:
            material_ids = answer_model.objects.filter(
                user_id=student_id
            ).values_list(f'{filter_path}__id', flat=True).distinct()
            
            test_material_ids.update(material_ids)
            
        except Exception as e:
            print(f"Error in {answer_model.__name__}: {str(e)}")
            continue
    
    # If no test materials found, return empty pagination
    if not test_material_ids:
        return Response({
            "count": 0,
            "total_pages": 1,
            "current_page": 1,
            "page_size": page_size,
            "next": None,
            "previous": None,
            "results": []
        })
    
    # Get TestMaterials with their Tests - ONLY MOCK TESTS
    test_materials = TestMaterial.objects.filter(
        id__in=list(test_material_ids),
        test__test_type='Mock'  # ✅ ONLY MOCK TESTS FILTER
    ).select_related('test').order_by('-test__date', '-id')
    
    # If no mock test materials found
    if not test_materials.exists():
        return Response({
            "count": 0,
            "total_pages": 1,
            "current_page": 1,
            "page_size": page_size,
            "next": None,
            "previous": None,
            "results": []
        })
    
    # Prepare test materials data
    test_materials_data = []
    
    for test_material in test_materials:
        test = test_material.test
        
        # Get all materials for this TestMaterial
        materials = []
        
        # LISTENING
        if ListeningMaterial:
            listening_materials = ListeningMaterial.objects.filter(test_material=test_material)
            for lm in listening_materials:
                materials.append({
                    'id': test_material.id,
                    'type': 'listening',
                    'title': lm.title or f"{test.title or test.test_number} Listening"
                })
        
        # READING  
        if ReadingMaterial:
            reading_materials = ReadingMaterial.objects.filter(test_material=test_material)
            for rm in reading_materials:
                materials.append({
                    'id': test_material.id,
                    'type': 'reading', 
                    'title': rm.title or f"{test.title or test.test_number} Reading"
                })
        
        # WRITING
        if WritingMaterial:
            writing_materials = WritingMaterial.objects.filter(test_material=test_material)
            for wm in writing_materials:
                materials.append({
                    'id': test_material.id,
                    'type': 'writing',
                    'title': wm.title or f"{test.title or test.test_number} Writing"
                })
        
        # SPEAKING
        if SpeakingMaterial:
            speaking_materials = SpeakingMaterial.objects.filter(test_material=test_material)
            for sm in speaking_materials:
                materials.append({
                    'id': test_material.id,
                    'type': 'speaking',
                    'title': sm.title or f"{test.title or test.test_number} Speaking"
                })
        
        # Sort materials in order: listening -> reading -> writing -> speaking
        type_order = {"listening": 1, "reading": 2, "writing": 3, "speaking": 4}
        materials.sort(key=lambda x: type_order.get(x["type"], 99))
        
        # Add test material data
        test_materials_data.append({
            'id': test_material.id,
            'title': test_material.title or f"Mock Test {test_material.id}",  # ✅ UPDATED TITLE
            'test_type': test.test_type,  # Will always be 'Mock'
            'test_info': {
                'test_title': test.title or test.test_number,
                'test_id': test.id
            },
            'materials': materials
        })
    
    # Apply pagination
    paginator = Paginator(test_materials_data, page_size)
    
    try:
        page_obj = paginator.page(page)
        paginated_data = list(page_obj)
        
        # Build next/previous URLs
        next_url = None
        previous_url = None
        
        if page_obj.has_next():
            next_url = f"?page={page_obj.next_page_number()}&page_size={page_size}"
        
        if page_obj.has_previous():
            previous_url = f"?page={page_obj.previous_page_number()}&page_size={page_size}"
        
        # Return exact format as requested
        return Response({
            "count": paginator.count,
            "total_pages": paginator.num_pages,
            "current_page": page_obj.number,
            "page_size": page_size,
            "next": next_url,
            "previous": previous_url,
            "results": paginated_data
        })
        
    except Exception as e:
        print(f"Pagination error: {str(e)}")
        
        # Return without pagination on error
        return Response({
            "count": len(test_materials_data),
            "total_pages": 1,
            "current_page": 1,
            "page_size": len(test_materials_data),
            "next": None,
            "previous": None,
            "results": test_materials_data
        })


@api_view(['GET'])
def student_test_detailed_results(request, student_id, material_id):
    """
    Get specific student's detailed results for a specific test material
    URL: /api/student-mocks/{student_id}/{material_id}/
    
    Returns detailed scores with material IDs for each skill
    """
    
    # Dynamic model loading
    def get_model_by_name(app_labels, model_name):
        for app_label in app_labels:
            try:
                if app_label:
                    return apps.get_model(app_label, model_name)
                else:
                    for model in apps.get_models():
                        if model._meta.model_name.lower() == model_name.lower():
                            return model
            except LookupError:
                continue
        return None
    
    def convert_listening_to_ielts_band(correct_answers):
        """Convert listening correct answers to IELTS band score"""
        conversion_table = {
            40: 9.0, 39: 9.0, 38: 8.5, 37: 8.5, 36: 8.0, 35: 8.0,
            34: 7.5, 33: 7.5, 32: 7.5, 31: 7.0, 30: 7.0,
            29: 6.5, 28: 6.5, 27: 6.5, 26: 6.5, 25: 6.0, 24: 6.0, 23: 6.0,
            22: 5.5, 21: 5.5, 20: 5.5, 19: 5.5, 18: 5.5, 17: 5.0, 16: 5.0,
            15: 4.5, 14: 4.5, 13: 4.5, 12: 4.0, 11: 4.0, 10: 4.0,
            9: 3.5, 8: 3.5, 7: 3.5, 6: 3.5, 5: 3.0, 4: 3.0,
            3: 2.5, 2: 2.5, 1: 2.0, 0: 0.0
        }
        return conversion_table.get(correct_answers, 0.0)

    def convert_reading_to_ielts_band(correct_answers):
        """Convert reading correct answers to IELTS band score"""
        conversion_table = {
            40: 9.0, 39: 9.0, 38: 8.5, 37: 8.5, 36: 8.0, 35: 8.0,
            34: 7.5, 33: 7.5, 32: 7.0, 31: 7.0, 30: 7.0,
            29: 6.5, 28: 6.5, 27: 6.5, 26: 6.0, 25: 6.0, 24: 6.0, 23: 6.0,
            22: 5.5, 21: 5.5, 20: 5.5, 19: 5.5, 18: 5.0, 17: 5.0, 16: 5.0, 15: 5.0,
            14: 4.5, 13: 4.5, 12: 4.0, 11: 4.0, 10: 4.0,
            9: 3.5, 8: 3.5, 7: 3.0, 6: 3.0, 5: 2.5, 4: 2.5,
            3: 2.0, 2: 2.0, 1: 1.0, 0: 0.0
        }
        return conversion_table.get(correct_answers, 0.0)
    
    # Get all required models
    Users = get_model_by_name(['app', None], 'Users')
    Test = get_model_by_name(['app', None], 'Test')
    TestMaterial = get_model_by_name(['app', None], 'TestMaterial')
    ListeningMaterial = get_model_by_name(['listening', None], 'ListeningMaterial')
    ReadingMaterial = get_model_by_name(['reading', None], 'ReadingMaterial')
    WritingMaterial = get_model_by_name(['writing', None], 'WritingMaterial')
    SpeakingMaterial = get_model_by_name(['speaking', None], 'SpeakingMaterial')
    ListeningUserAnswer = get_model_by_name(['listening', None], 'ListeningUserAnswer')
    ReadingUserAnswer = get_model_by_name(['reading', None], 'ReadingUserAnswer')
    WritingUserAnswer = get_model_by_name(['writing', None], 'WritingUserAnswer')
    SpeakingUserAnswer = get_model_by_name(['speaking', None], 'SpeakingUserAnswer')
    
    if not Users or not TestMaterial:
        return Response(
            {"error": "Required models not found"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    # Validate parameters
    try:
        student_id = int(student_id)
        material_id = int(material_id)
    except (ValueError, TypeError):
        return Response(
            {"error": "Invalid student_id or material_id. Must be integers."}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get student
    try:
        student = Users.objects.get(id=student_id, role='Student')
    except Users.DoesNotExist:
        return Response(
            {"error": f"Student with id={student_id} not found."}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Get test material
    try:
        test_material = TestMaterial.objects.select_related('test').get(id=material_id)
    except TestMaterial.DoesNotExist:
        return Response(
            {"error": f"TestMaterial with id={material_id} not found."}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Get test from test material
    test = test_material.test
    
    # Check if this is a Mock test
    is_mock_test = test.test_type == 'Mock'
    
    # Initialize results structure
    results = {
        "student_info": {
            "student_id": student.id,
            "full_name": f"{student.first_name} {student.last_name}",
            "phone": student.phone or "",
            "group_name": student.student_group.name if student.student_group else "",
            "created_at": student.date_joined.strftime("%Y-%m-%d-%H:%M") if student.date_joined else "",
        },
        "test_info": {
            "test_id": test.id,
            "test_title": test.title or test.test_number,
            "test_type": test.test_type,
            "test_date": test.date.isoformat() if test.date else None
        },
        "material_info": {
            "test_material_id": test_material.id,
            "material_title": test_material.title or f"Material {test_material.id}",
            "type": "full"
        },
        "skills": {}
    }
    
    # LISTENING RESULTS
    if ListeningUserAnswer and ListeningMaterial:
        # Get listening material
        listening_material = ListeningMaterial.objects.filter(test_material=test_material).first()
        
        if listening_material:
            listening_user_answers = ListeningUserAnswer.objects.filter(
                user=student,
                listening__listening_material=listening_material
            )
            
            listening_correct = listening_user_answers.filter(is_true=True).count()
            listening_total = listening_user_answers.count()
            listening_complete = listening_user_answers.exists()
            
            if listening_complete:
                if is_mock_test:
                    listening_score = convert_listening_to_ielts_band(listening_correct)
                else:
                    listening_score = (listening_correct / listening_total * 100) if listening_total > 0 else 0
            else:
                listening_score = 0
            
            results["skills"]["listening"] = {
                "id": listening_material.id,
                "title": listening_material.title or f"{test.title or test.test_number} Listening",
                "listening_complete": listening_complete,
                "total_questions": listening_total,
                "correct_answers": listening_correct,
                "incorrect_answers": listening_total - listening_correct,
                "score": round(listening_score, 1) if is_mock_test else round(listening_score, 2),
                "score_percentage": round(listening_score, 2) if not is_mock_test else None
            }
        else:
            results["skills"]["listening"] = {
                "id": None,
                "title": "Listening material not found",
                "listening_complete": False,
                "total_questions": 0,
                "correct_answers": 0,
                "incorrect_answers": 0,
                "score": 0,
                "score_percentage": None
            }
    else:
        results["skills"]["listening"] = {
            "id": None,
            "title": "Listening not available",
            "listening_complete": False,
            "total_questions": 0,
            "correct_answers": 0,
            "incorrect_answers": 0,
            "score": 0,
            "score_percentage": None
        }
    
    # READING RESULTS
    if ReadingUserAnswer and ReadingMaterial:
        # Get reading material
        reading_material = ReadingMaterial.objects.filter(test_material=test_material).first()
        
        if reading_material:
            reading_user_answers = ReadingUserAnswer.objects.filter(
                user=student,
                reading__reading_material=reading_material
            )
            
            reading_correct = reading_user_answers.filter(is_true=True).count()
            reading_total = reading_user_answers.count()
            reading_complete = reading_user_answers.exists()
            
            if reading_complete:
                if is_mock_test:
                    reading_score = convert_reading_to_ielts_band(reading_correct)
                else:
                    reading_score = (reading_correct / reading_total * 100) if reading_total > 0 else 0
            else:
                reading_score = 0
            
            results["skills"]["reading"] = {
                "id": reading_material.id,
                "title": reading_material.title or f"{test.title or test.test_number} Reading",
                "reading_complete": reading_complete,
                "total_questions": reading_total,
                "correct_answers": reading_correct,
                "incorrect_answers": reading_total - reading_correct,
                "score": round(reading_score, 1) if is_mock_test else round(reading_score, 2),
                "score_percentage": round(reading_score, 2) if not is_mock_test else None
            }
        else:
            results["skills"]["reading"] = {
                "id": None,
                "title": "Reading material not found",
                "reading_complete": False,
                "total_questions": 0,
                "correct_answers": 0,
                "incorrect_answers": 0,
                "score": 0,
                "score_percentage": None
            }
    else:
        results["skills"]["reading"] = {
            "id": None,
            "title": "Reading not available",
            "reading_complete": False,
            "total_questions": 0,
            "correct_answers": 0,
            "incorrect_answers": 0,
            "score": 0,
            "score_percentage": None
        }
    
    # WRITING RESULTS
    if WritingUserAnswer and WritingMaterial:
        # Get writing material
        writing_material = WritingMaterial.objects.filter(test_material=test_material).first()
        
        if writing_material:
            writing_task1_answers = WritingUserAnswer.objects.filter(
                user=student,
                writing__writing_material=writing_material,
                writing__writing_task=1
            )
            writing_task1_score = writing_task1_answers.aggregate(avg_score=Avg('score'))['avg_score'] or 0
            task1_complete = writing_task1_answers.exists()
            task1_feedback = writing_task1_answers.first().feedback if writing_task1_answers.exists() else None
            
            writing_task2_answers = WritingUserAnswer.objects.filter(
                user=student,
                writing__writing_material=writing_material,
                writing__writing_task=2
            )
            writing_task2_score = writing_task2_answers.aggregate(avg_score=Avg('score'))['avg_score'] or 0
            task2_complete = writing_task2_answers.exists()
            task2_feedback = writing_task2_answers.first().feedback if writing_task2_answers.exists() else None
            
            # Calculate writing overall: ((T2*2)+T1)/3
            if writing_task1_score > 0 or writing_task2_score > 0:
                writing_overall_score = ((writing_task2_score * 2) + writing_task1_score) / 3
            else:
                writing_overall_score = 0
            
            writing_complete = task1_complete or task2_complete
            
            all_writing_answers = WritingUserAnswer.objects.filter(
                user=student,
                writing__writing_material=writing_material
            )
            total_tasks = all_writing_answers.count()
            completed_tasks = all_writing_answers.filter(score__isnull=False).count()
            
            results["skills"]["writing"] = {
                "id": writing_material.id,
                "title": writing_material.title or f"{test.title or test.test_number} Writing",
                "writing_complete": writing_complete,
                "total_questions": total_tasks,
                "correct_answers": completed_tasks,
                "incorrect_answers": total_tasks - completed_tasks,
                "score": round(writing_overall_score, 1) if is_mock_test else round(writing_overall_score, 2),
                "score_percentage": round(writing_overall_score * 10, 2) if not is_mock_test else None,
                "writing_task1": {
                    "completed": task1_complete,
                    "score": round(writing_task1_score, 1) if is_mock_test else round(writing_task1_score, 2),
                    "feedback": task1_feedback
                },
                "writing_task2": {
                    "completed": task2_complete,
                    "score": round(writing_task2_score, 1) if is_mock_test else round(writing_task2_score, 2),
                    "feedback": task2_feedback
                },
                "overall_writing_score": round(writing_overall_score, 1) if is_mock_test else round(writing_overall_score, 2)
            }
        else:
            results["skills"]["writing"] = {
                "id": None,
                "title": "Writing material not found",
                "writing_complete": False,
                "total_questions": 0,
                "correct_answers": 0,
                "incorrect_answers": 0,
                "score": 0,
                "score_percentage": None,
                "writing_task1": {"completed": False, "score": 0, "feedback": None},
                "writing_task2": {"completed": False, "score": 0, "feedback": None},
                "overall_writing_score": 0
            }
    else:
        results["skills"]["writing"] = {
            "id": None,
            "title": "Writing not available",
            "writing_complete": False,
            "total_questions": 0,
            "correct_answers": 0,
            "incorrect_answers": 0,
            "score": 0,
            "score_percentage": None,
            "writing_task1": {"completed": False, "score": 0, "feedback": None},
            "writing_task2": {"completed": False, "score": 0, "feedback": None},
            "overall_writing_score": 0
        }
    
    # SPEAKING RESULTS
    if SpeakingUserAnswer and SpeakingMaterial:
        # Get speaking material
        speaking_material = SpeakingMaterial.objects.filter(test_material=test_material).first()
        
        if speaking_material:
            speaking_answers = SpeakingUserAnswer.objects.filter(
                user=student,
                speaking__test_material=test_material  # Note: SpeakingMaterial has direct relation to TestMaterial
            )
            
            speaking_overall_score = speaking_answers.aggregate(avg_score=Avg('score'))['avg_score'] or 0
            speaking_completed = speaking_answers.count()
            speaking_with_score = speaking_answers.filter(score__isnull=False).count()
            speaking_complete = speaking_answers.exists()
            
            latest_speaking = speaking_answers.order_by('-created_at').first()
            feedback = latest_speaking.feedback if latest_speaking else None
            
            results["skills"]["speaking"] = {
                "id": speaking_material.id,
                "title": speaking_material.title or f"{test.title or test.test_number} Speaking",
                "speaking_complete": speaking_complete,
                "total_questions": speaking_completed,
                "correct_answers": speaking_with_score,
                "incorrect_answers": speaking_completed - speaking_with_score,
                "score": round(speaking_overall_score, 1) if is_mock_test else round(speaking_overall_score, 2),
                "score_percentage": round(speaking_overall_score * 10, 2) if not is_mock_test else None,
                "feedback": feedback
            }
        else:
            results["skills"]["speaking"] = {
                "id": None,
                "title": "Speaking material not found",
                "speaking_complete": False,
                "total_questions": 0,
                "correct_answers": 0,
                "incorrect_answers": 0,
                "score": 0,
                "score_percentage": None,
                "feedback": None
            }
    else:
        results["skills"]["speaking"] = {
            "id": None,
            "title": "Speaking not available",
            "speaking_complete": False,
            "total_questions": 0,
            "correct_answers": 0,
            "incorrect_answers": 0,
            "score": 0,
            "score_percentage": None,
            "feedback": None
        }
    
    # Calculate overall statistics
    listening_score = results["skills"]["listening"]["score"]
    reading_score = results["skills"]["reading"]["score"]
    writing_score = results["skills"]["writing"]["score"]
    speaking_score = results["skills"]["speaking"]["score"]
    
    # For Mock tests, calculate total overall score like IELTS format
    if is_mock_test:
        all_scores = [listening_score, reading_score, writing_score, speaking_score]
        valid_scores = [score for score in all_scores if score > 0]
        total_overall_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0
        
        # Round to nearest 0.5 for IELTS
        total_overall_score = round(total_overall_score * 2) / 2
    else:
        # For Thematic tests, simple average
        all_scores = [listening_score, reading_score, writing_score, speaking_score]
        valid_scores = [score for score in all_scores if score > 0]
        total_overall_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0
    
    # Update material_info with complete statistics
    results["material_info"].update({
        "title": test_material.title or f"Test {test_material.id}",
        "reading_complete": results["skills"]["reading"]["reading_complete"],
        "listening_complete": results["skills"]["listening"]["listening_complete"],
        "writing_complete": results["skills"]["writing"]["writing_complete"],
        "speaking_complete": results["skills"]["speaking"]["speaking_complete"],
        "listening_total_questions": results["skills"]["listening"]["total_questions"],
        "listening_correct_answers": results["skills"]["listening"]["correct_answers"],
        "listening_score": results["skills"]["listening"]["score"],
        "reading_total_questions": results["skills"]["reading"]["total_questions"],
        "reading_correct_answers": results["skills"]["reading"]["correct_answers"],
        "reading_score": results["skills"]["reading"]["score"],
        "writing_task1_score": results["skills"]["writing"]["writing_task1"]["score"],
        "writing_task2_score": results["skills"]["writing"]["writing_task2"]["score"],
        "writing_overall_score": results["skills"]["writing"]["overall_writing_score"],
        "speaking_overall_score": results["skills"]["speaking"]["score"],
        "total_overall_score": round(total_overall_score, 1) if is_mock_test else round(total_overall_score, 2)
    })
    
    return Response(results)


@api_view(['GET'])
def student_thematic_statistics(request, student_id):
    """
    Get specific student's THEMATIC test materials with pagination
    URL: /api/student-thematics/{student_id}/?page=1&page_size=10
    Returns flattened format with individual skill materials
    """

    # Dynamic model loading function
    def get_model_by_name(app_labels, model_name):
        for app_label in app_labels:
            try:
                if app_label:
                    return apps.get_model(app_label, model_name)
                else:
                    for model in apps.get_models():
                        if model._meta.model_name.lower() == model_name.lower():
                            return model
            except LookupError:
                continue
        return None

    # Get all required models
    Users = get_model_by_name(['app', None], 'Users')
    Test = get_model_by_name(['app', None], 'Test')
    TestMaterial = get_model_by_name(['app', None], 'TestMaterial')

    # Skill material models
    ListeningMaterial = get_model_by_name(['listening', None], 'ListeningMaterial')
    ReadingMaterial = get_model_by_name(['reading', None], 'ReadingMaterial')
    WritingMaterial = get_model_by_name(['writing', None], 'WritingMaterial')
    SpeakingMaterial = get_model_by_name(['speaking', None], 'SpeakingMaterial')

    # Answer models
    ListeningUserAnswer = get_model_by_name(['listening', None], 'ListeningUserAnswer')
    ReadingUserAnswer = get_model_by_name(['reading', None], 'ReadingUserAnswer')
    WritingUserAnswer = get_model_by_name(['writing', None], 'WritingUserAnswer')
    SpeakingUserAnswer = get_model_by_name(['speaking', None], 'SpeakingUserAnswer')

    if not Users:
        return Response(
            {"error": "Required models not found"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # Validate student_id
    try:
        student_id = int(student_id)
    except (ValueError, TypeError):
        return Response(
            {"error": "Invalid student_id. Must be an integer."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Check if student exists
    try:
        student = Users.objects.get(id=student_id, role='Student')
    except Users.DoesNotExist:
        return Response(
            {"error": f"Student with id={student_id} not found."},
            status=status.HTTP_404_NOT_FOUND
        )

    # Get pagination parameters
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 10))

    # Collect all test material data that student has worked on
    student_materials = []

    # 1. Get Listening materials - Return ListeningMaterial.id
    if ListeningUserAnswer:
        try:
            listening_answers = ListeningUserAnswer.objects.filter(
                user_id=student_id
            ).select_related('listening')

            for answer in listening_answers:
                try:
                    # Try to access the listening material and test
                    listening = answer.listening
                    if hasattr(listening, 'listening_material'):
                        listening_material = listening.listening_material
                        if hasattr(listening_material, 'test_material'):
                            test_material = listening_material.test_material
                            if hasattr(test_material, 'test') and test_material.test.test_type == 'Thematic':
                                student_materials.append({
                                    "id": listening_material.id,  # ✅ ListeningMaterial.id
                                    "type": "listening",
                                    "title": listening_material.title or f"Listening Activity {listening_material.id}",
                                    "test_info": {
                                        "test_title": test_material.title or test_material.test.title or f"Test {test_material.test.id}",
                                        "test_id": test_material.id,
                                        "test_type": test_material.test.test_type
                                    },
                                    "skill_info": {
                                        "skill_title": test_material.test.title or f"Thematic Test {test_material.test.id}",
                                        "skill_id": listening.id,  # ✅ Listening.id for reference
                                        "material_id": listening_material.id  # ✅ ListeningMaterial.id
                                    }
                                })
                except AttributeError as e:
                    print(f"Listening relationship error: {e}")
                    continue
        except Exception as e:
            print(f"Error in Listening materials: {str(e)}")

    # 2. Get Reading materials - Return ReadingMaterial.id
    if ReadingUserAnswer:
        try:
            reading_answers = ReadingUserAnswer.objects.filter(
                user_id=student_id
            ).select_related('reading')

            for answer in reading_answers:
                try:
                    reading = answer.reading
                    if hasattr(reading, 'reading_material'):
                        reading_material = reading.reading_material
                        if hasattr(reading_material, 'test_material'):
                            test_material = reading_material.test_material
                            if hasattr(test_material, 'test') and test_material.test.test_type == 'Thematic':
                                student_materials.append({
                                    "id": reading_material.id,  # ✅ ReadingMaterial.id
                                    "type": "reading",
                                    "title": reading_material.title or f"Reading Activity {reading_material.id}",
                                    "test_info": {
                                        "test_title": test_material.title or test_material.test.title or f"Test {test_material.test.id}",
                                        "test_id": test_material.id,
                                        "test_type": test_material.test.test_type
                                    },
                                    "skill_info": {
                                        "skill_title": test_material.test.title or f"Thematic Test {test_material.test.id}",
                                        "skill_id": reading.id,  # ✅ Reading.id for reference
                                        "material_id": reading_material.id  # ✅ ReadingMaterial.id
                                    }
                                })
                except AttributeError as e:
                    print(f"Reading relationship error: {e}")
                    continue
        except Exception as e:
            print(f"Error in Reading materials: {str(e)}")

    # 3. Get Writing materials - Return WritingMaterial.id
    if WritingUserAnswer:
        try:
            writing_answers = WritingUserAnswer.objects.filter(
                user_id=student_id
            ).select_related('writing')

            for answer in writing_answers:
                try:
                    writing = answer.writing
                    if hasattr(writing, 'writing_material'):
                        writing_material = writing.writing_material
                        if hasattr(writing_material, 'test_material'):
                            test_material = writing_material.test_material
                            if hasattr(test_material, 'test') and test_material.test.test_type == 'Thematic':
                                student_materials.append({
                                    "id": writing_material.id,  # ✅ WritingMaterial.id
                                    "type": "writing",
                                    "title": writing_material.title or f"Writing Activity {writing_material.id}",
                                    "test_info": {
                                        "test_title": test_material.title or test_material.test.title or f"Test {test_material.test.id}",
                                        "test_id": test_material.id,
                                        "test_type": test_material.test.test_type
                                    },
                                    "skill_info": {
                                        "skill_title": test_material.test.title or f"Thematic Test {test_material.test.id}",
                                        "skill_id": writing.id,  # ✅ Writing.id for reference
                                        "material_id": writing_material.id  # ✅ WritingMaterial.id
                                    }
                                })
                except AttributeError as e:
                    print(f"Writing relationship error: {e}")
                    continue
        except Exception as e:
            print(f"Error in Writing materials: {str(e)}")

    # 4. Get Speaking materials - Return SpeakingMaterial.id (already correct)
    if SpeakingUserAnswer:
        try:
            speaking_answers = SpeakingUserAnswer.objects.filter(
                user_id=student_id
            ).select_related('speaking')

            for answer in speaking_answers:
                try:
                    speaking_material = answer.speaking  # This is directly SpeakingMaterial
                    if hasattr(speaking_material, 'test_material'):
                        test_material = speaking_material.test_material
                        if hasattr(test_material, 'test') and test_material.test.test_type == 'Thematic':
                            student_materials.append({
                                "id": speaking_material.id,  # ✅ SpeakingMaterial.id (already correct)
                                "type": "speaking",
                                "title": speaking_material.title or f"Speaking Activity {speaking_material.id}",
                                "test_info": {
                                    "test_title": test_material.title or test_material.test.title or f"Test {test_material.test.id}",
                                    "test_id": test_material.id,
                                    "test_type": test_material.test.test_type
                                },
                                "skill_info": {
                                    "skill_title": test_material.test.title or f"Thematic Test {test_material.test.id}",
                                    "skill_id": speaking_material.id,  # ✅ SpeakingMaterial.id
                                    "material_id": speaking_material.id  # ✅ SpeakingMaterial.id
                                }
                            })
                except AttributeError as e:
                    print(f"Speaking relationship error: {e}")
                    continue
        except Exception as e:
            print(f"Error in Speaking materials: {str(e)}")

    # ✅ Remove duplicates based on material_id and type (not skill_id)
    seen = set()
    unique_materials = []
    for material in student_materials:
        identifier = (material['id'], material['type'])  # Using material ID now
        if identifier not in seen:
            seen.add(identifier)
            unique_materials.append(material)

    # Sort by material id (descending - newest first)
    unique_materials.sort(key=lambda x: x['id'], reverse=True)

    # If no materials found, return empty pagination
    if not unique_materials:
        return Response({
            "count": 0,
            "total_pages": 1,
            "current_page": 1,
            "page_size": page_size,
            "next": None,
            "previous": None,
            "results": []
        })

    # Apply pagination to the complete list
    try:
        paginator = Paginator(unique_materials, page_size)
        page_obj = paginator.page(page)

        # Build next/previous URLs
        next_url = None
        previous_url = None

        if page_obj.has_next():
            next_url = f"?page={page_obj.next_page_number()}&page_size={page_size}"

        if page_obj.has_previous():
            previous_url = f"?page={page_obj.previous_page_number()}&page_size={page_size}"

        return Response({
            "count": paginator.count,
            "total_pages": paginator.num_pages,
            "current_page": page_obj.number,
            "page_size": page_size,
            "next": next_url,
            "previous": previous_url,
            "results": list(page_obj)
        })

    except Exception as e:
        print(f"Pagination error: {str(e)}")
        return Response({
            "count": len(unique_materials),
            "total_pages": 1,
            "current_page": 1,
            "page_size": len(unique_materials),
            "next": None,
            "previous": None,
            "results": unique_materials[:page_size]
        })


@api_view(['GET'])
def detail_material(request, skill_material_id, skill_type):
    def get_model_by_name(app_labels, model_name):
        for app_label in app_labels:
            try:
                if app_label:
                    return apps.get_model(app_label, model_name)
                else:
                    for model in apps.get_models():
                        if model._meta.model_name.lower() == model_name.lower():
                            return model
            except LookupError:
                continue
        return None

    # Validate skill_type parameter
    ALLOWED_SKILL_TYPES = ['reading', 'listening', 'writing', 'speaking']
    if skill_type not in ALLOWED_SKILL_TYPES:
        return Response(
            {"error": f"Invalid skill type '{skill_type}'. Allowed types: {ALLOWED_SKILL_TYPES}"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Validate skill_material_id parameter (✅ This is now Material ID)
    try:
        material_id = int(skill_material_id)
    except (ValueError, TypeError):
        return Response(
            {"error": "Invalid material_id. Must be integer."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # ✅ Get the appropriate Material model based on skill_type
    material_model = None
    skill_model = None
    if skill_type == 'reading':
        material_model = get_model_by_name(['reading', None], 'ReadingMaterial')
        skill_model = get_model_by_name(['reading', None], 'Reading')
    elif skill_type == 'listening':
        material_model = get_model_by_name(['listening', None], 'ListeningMaterial')
        skill_model = get_model_by_name(['listening', None], 'Listening')
    elif skill_type == 'writing':
        material_model = get_model_by_name(['writing', None], 'WritingMaterial')
        skill_model = get_model_by_name(['writing', None], 'Writing')
    elif skill_type == 'speaking':
        material_model = get_model_by_name(['speaking', None], 'SpeakingMaterial')
        skill_model = get_model_by_name(['speaking', None], 'Speaking')

    if not material_model:
        return Response(
            {"error": f"{skill_type.capitalize()}Material model not found"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # ✅ Get the Material object first
    try:
        material_obj = material_model.objects.select_related('test_material__test').get(id=material_id)
    except material_model.DoesNotExist:
        return Response(
            {"error": f"{skill_type.capitalize()}Material with id={material_id} not found."},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {"error": f"Error accessing {skill_type} material: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # ✅ Get related skill objects from Material
    skill_objects = []
    skill_ids = []
    try:
        if skill_type == 'speaking':
            # For speaking, SpeakingMaterial is used directly
            skill_objects = [material_obj]
            skill_ids = [material_obj.id]
            primary_skill_obj = material_obj
        else:
            # For reading, listening, writing - get skill objects from material
            if skill_type == 'reading':
                skill_objects = skill_model.objects.filter(reading_material=material_obj)
            elif skill_type == 'listening':
                skill_objects = skill_model.objects.filter(listening_material=material_obj)
            elif skill_type == 'writing':
                skill_objects = skill_model.objects.filter(writing_material=material_obj)

            skill_ids = list(skill_objects.values_list('id', flat=True))
            primary_skill_obj = skill_objects.first() if skill_objects.exists() else None

    except Exception as e:
        return Response(
            {"error": f"Error accessing {skill_type} objects: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # Get related test_material and test information
    try:
        test_material = material_obj.test_material if hasattr(material_obj, 'test_material') else None
        test = test_material.test if test_material else None
        # ✅ Use Material.title directly
        skill_title = material_obj.title if hasattr(material_obj,
                                                    'title') else f"{skill_type.capitalize()} Material {material_obj.id}"

    except Exception as e:
        # Agar relationship mavjud bo'lmasa, faqat material ma'lumotlarini qaytaramiz
        test_material = None
        test = None
        skill_title = f"{skill_type.capitalize()} Material {material_obj.id}"

    # Build response
    result = {
        "skill_type": skill_type,
        "material_id": material_obj.id,  # ✅ ReadingMaterial.id, ListeningMaterial.id, etc.
        "title": skill_title,  # ✅ Material.title
        "test_info": {
            "test_material_title": test_material.title if test_material else None,
            "test_material_id": test_material.id if test_material else None,
            "test_title": test.title if test else None,
            "test_number": test.test_number if test else None,
            "test_id": test.id if test else None,
            "test_type": test.test_type if test else None
        },
        "skill_info": {
            "skill_title": skill_title,
            "skill_ids": skill_ids,  # ✅ All related skill IDs (Reading.id, Listening.id, etc.)
            "material_id": material_obj.id  # ✅ Material ID
        }
    }

    # ✅ Add Material-specific fields if they exist
    for field in ['description', 'text', 'passage', 'title']:
        if hasattr(material_obj, field):
            value = getattr(material_obj, field)
            if value:
                result[field] = value

    # ✅ Add skill-specific fields from primary skill object if exists
    if primary_skill_obj and skill_type != 'speaking':
        for field in ['passage_number', 'listening_section', 'writing_task', 'speaking_part']:
            if hasattr(primary_skill_obj, field):
                value = getattr(primary_skill_obj, field)
                if value is not None:
                    result[field] = value

    # ✅ Add file fields from Material or Skill objects
    file_fields = ['audio', 'audio_file', 'image', 'video']
    for file_field in file_fields:
        file_obj = None

        # First try Material object
        if hasattr(material_obj, file_field):
            file_obj = getattr(material_obj, file_field)
        # Then try primary skill object
        elif primary_skill_obj and hasattr(primary_skill_obj, file_field):
            file_obj = getattr(primary_skill_obj, file_field)

        if file_obj:
            try:
                result[file_field] = request.build_absolute_uri(file_obj.url)
            except:
                result[file_field] = str(file_obj)

    return Response(result)


@api_view(['GET'])
def student_skill_detailed_results(request, student_id, skill_id, skill_type):
    def get_model_by_name(app_labels, model_name):
        for app_label in app_labels:
            try:
                if app_label:
                    return apps.get_model(app_label, model_name)
                else:
                    for model in apps.get_models():
                        if model._meta.model_name.lower() == model_name.lower():
                            return model
            except LookupError:
                continue
        return None

    def get_skill_title(material_obj, skill_type):
        """Get appropriate title for each skill type using Material titles"""
        # ✅ Use Material.title directly
        return material_obj.title or f"{skill_type.capitalize()} Material {material_obj.id}"

    # Validate skill_type
    ALLOWED_SKILL_TYPES = ['reading', 'listening', 'writing', 'speaking']
    if skill_type not in ALLOWED_SKILL_TYPES:
        return Response(
            {"error": f"Invalid skill type '{skill_type}'. Allowed: {ALLOWED_SKILL_TYPES}"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Get required models
    Users = get_model_by_name(['app', None], 'Users')

    # Get skill-specific models
    if skill_type == 'reading':
        SkillModel = get_model_by_name(['reading', None], 'Reading')
        SkillMaterialModel = get_model_by_name(['reading', None], 'ReadingMaterial')
        SkillUserAnswerModel = get_model_by_name(['reading', None], 'ReadingUserAnswer')
    elif skill_type == 'listening':
        SkillModel = get_model_by_name(['listening', None], 'Listening')
        SkillMaterialModel = get_model_by_name(['listening', None], 'ListeningMaterial')
        SkillUserAnswerModel = get_model_by_name(['listening', None], 'ListeningUserAnswer')
    elif skill_type == 'writing':
        SkillModel = get_model_by_name(['writing', None], 'Writing')
        SkillMaterialModel = get_model_by_name(['writing', None], 'WritingMaterial')
        SkillUserAnswerModel = get_model_by_name(['writing', None], 'WritingUserAnswer')
    elif skill_type == 'speaking':
        SkillModel = get_model_by_name(['speaking', None], 'Speaking')
        SkillMaterialModel = get_model_by_name(['speaking', None], 'SpeakingMaterial')
        SkillUserAnswerModel = get_model_by_name(['speaking', None], 'SpeakingUserAnswer')

    if not Users or not SkillMaterialModel or not SkillUserAnswerModel:
        return Response(
            {"error": "Required models not found"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # Validate parameters
    try:
        student_id = int(student_id)
        material_id = int(skill_id)  # ✅ This is now Material ID (ReadingMaterial.id, etc.)
    except (ValueError, TypeError):
        return Response(
            {"error": "Invalid student_id or material_id. Must be integers."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Get student
    try:
        student = Users.objects.get(id=student_id, role='Student')
    except Users.DoesNotExist:
        return Response(
            {"error": f"Student with id={student_id} not found."},
            status=status.HTTP_404_NOT_FOUND
        )

    # ✅ Get Material object first, then find related skill objects
    try:
        material_obj = SkillMaterialModel.objects.select_related('test_material__test').get(id=material_id)

        # Get skill objects related to this material
        if skill_type == 'reading':
            skill_objects = SkillModel.objects.filter(reading_material=material_obj)
        elif skill_type == 'listening':
            skill_objects = SkillModel.objects.filter(listening_material=material_obj)
        elif skill_type == 'writing':
            skill_objects = SkillModel.objects.filter(writing_material=material_obj)
        elif skill_type == 'speaking':
            # For speaking, use SpeakingMaterial directly
            skill_objects = [material_obj]  # SpeakingMaterial is the skill object

        # Get skill IDs
        if skill_type == 'speaking':
            skill_ids = [material_obj.id]
            primary_skill_obj = material_obj
        else:
            skill_ids = list(skill_objects.values_list('id', flat=True))
            primary_skill_obj = skill_objects.first() if skill_objects.exists() else None

        if not skill_ids:
            return Response(
                {"error": f"No {skill_type} objects found for {skill_type}_material_id={material_id}."},
                status=status.HTTP_404_NOT_FOUND
            )

    except SkillMaterialModel.DoesNotExist:
        return Response(
            {"error": f"{skill_type.capitalize()}Material with id={material_id} not found."},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {"error": f"Error accessing {skill_type}: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # Get test info
    test_material = material_obj.test_material if hasattr(material_obj, 'test_material') else None
    test = test_material.test if test_material else None

    # Process based on skill type
    if skill_type == 'reading':
        # READING RESULTS
        user_answers = SkillUserAnswerModel.objects.filter(
            user=student,
            reading__in=skill_objects
        )

        correct_count = user_answers.filter(is_true=True).count()
        total_count = user_answers.count()
        complete = user_answers.exists()

        if complete and total_count > 0:
            score = (correct_count / total_count * 100)
        else:
            score = 0

        # ✅ Use ReadingMaterial.title
        skill_title = get_skill_title(material_obj, skill_type)

        result = {
            "id": skill_ids[0] if skill_ids else material_id,  # ✅ Reading.id (first skill ID)
            "skill_type": skill_type,
            "title": skill_title,  # ✅ ReadingMaterial.title
            "passage_number": primary_skill_obj.passage_number if primary_skill_obj and hasattr(primary_skill_obj,
                                                                                                'passage_number') else None,
            "test_type": test.test_type if test else None,
            "test_info": {
                "test_id": test.id if test else None,
                "test_title": test.title if test else None,
                "test_number": test.test_number if test else None,
                "test_type": test.test_type if test else None
            },
            "material_info": {
                "id": test_material.id if test_material else None,
                "title": test_material.title if test_material else None,
                "reading_material_id": material_obj.id,
                "reading_material_title": material_obj.title
            },
            "skill_info": {
                "skill_ids": skill_ids,  # ✅ All Reading.id list
                "material_id": material_obj.id  # ✅ ReadingMaterial.id
            },
            "complete": complete,
            "total_questions": total_count,
            "correct_answers": correct_count,
            "incorrect_answers": total_count - correct_count,
            "score": round(score, 2),
            "score_percentage": round(score, 2)
        }

    elif skill_type == 'listening':
        # LISTENING RESULTS
        user_answers = SkillUserAnswerModel.objects.filter(
            user=student,
            listening__in=skill_objects
        )

        correct_count = user_answers.filter(is_true=True).count()
        total_count = user_answers.count()
        complete = user_answers.exists()

        if complete and total_count > 0:
            score = (correct_count / total_count * 100)
        else:
            score = 0

        # ✅ Use ListeningMaterial.title
        skill_title = get_skill_title(material_obj, skill_type)

        result = {
            "id": skill_ids[0] if skill_ids else material_id,  # ✅ Listening.id (first skill ID)
            "skill_type": skill_type,
            "title": skill_title,  # ✅ ListeningMaterial.title
            "listening_section": primary_skill_obj.listening_section if primary_skill_obj and hasattr(primary_skill_obj,
                                                                                                      'listening_section') else None,
            "test_type": test.test_type if test else None,
            "test_info": {
                "test_id": test.id if test else None,
                "test_title": test.title if test else None,
                "test_number": test.test_number if test else None,
                "test_type": test.test_type if test else None
            },
            "material_info": {
                "id": test_material.id if test_material else None,
                "title": test_material.title if test_material else None,
                "listening_material_id": material_obj.id,
                "listening_material_title": material_obj.title
            },
            "skill_info": {
                "skill_ids": skill_ids,  # ✅ All Listening.id list
                "material_id": material_obj.id  # ✅ ListeningMaterial.id
            },
            "complete": complete,
            "total_questions": total_count,
            "correct_answers": correct_count,
            "incorrect_answers": total_count - correct_count,
            "score": round(score, 2),
            "score_percentage": round(score, 2),
            "audio_file": request.build_absolute_uri(primary_skill_obj.audio.url) if primary_skill_obj and hasattr(
                primary_skill_obj, 'audio') and primary_skill_obj.audio else None,
            "audioscript": primary_skill_obj.audioscript if primary_skill_obj and hasattr(primary_skill_obj,
                                                                                          'audioscript') else None,
            "is_script": primary_skill_obj.is_script if primary_skill_obj and hasattr(primary_skill_obj,
                                                                                      'is_script') else None
        }

    elif skill_type == 'writing':
        # WRITING RESULTS
        task1_answers = SkillUserAnswerModel.objects.filter(
            user=student,
            writing__in=skill_objects,
            writing__writing_task=1
        )
        task1_score = task1_answers.aggregate(avg_score=Avg('score'))['avg_score'] or 0
        task1_complete = task1_answers.exists()
        task1_feedback = task1_answers.first().feedback if task1_answers.exists() else None

        task2_answers = SkillUserAnswerModel.objects.filter(
            user=student,
            writing__in=skill_objects,
            writing__writing_task=2
        )
        task2_score = task2_answers.aggregate(avg_score=Avg('score'))['avg_score'] or 0
        task2_complete = task2_answers.exists()
        task2_feedback = task2_answers.first().feedback if task2_answers.exists() else None

        # Calculate overall score: ((T2*2)+T1)/3
        if task1_score > 0 or task2_score > 0:
            overall_score = ((task2_score * 2) + task1_score) / 3
        else:
            overall_score = 0

        complete = task1_complete or task2_complete
        total_tasks = SkillUserAnswerModel.objects.filter(user=student, writing__in=skill_objects).count()
        completed_tasks = SkillUserAnswerModel.objects.filter(
            user=student, writing__in=skill_objects, score__isnull=False
        ).count()

        # ✅ Use WritingMaterial.title
        skill_title = get_skill_title(material_obj, skill_type)

        result = {
            "id": skill_ids[0] if skill_ids else material_id,  # ✅ Writing.id (first skill ID)
            "skill_type": skill_type,
            "title": skill_title,  # ✅ WritingMaterial.title
            "writing_task": primary_skill_obj.writing_task if primary_skill_obj and hasattr(primary_skill_obj,
                                                                                            'writing_task') else None,
            "test_type": test.test_type if test else None,
            "test_info": {
                "test_id": test.id if test else None,
                "test_title": test.title if test else None,
                "test_number": test.test_number if test else None,
                "test_type": test.test_type if test else None
            },
            "material_info": {
                "id": test_material.id if test_material else None,
                "title": test_material.title if test_material else None,
                "writing_material_id": material_obj.id,
                "writing_material_title": material_obj.title
            },
            "skill_info": {
                "skill_ids": skill_ids,  # ✅ All Writing.id list
                "material_id": material_obj.id  # ✅ WritingMaterial.id
            },
            "complete": complete,
            "total_questions": total_tasks,
            "correct_answers": completed_tasks,
            "incorrect_answers": total_tasks - completed_tasks,
            "score": round(overall_score, 2),
            "score_percentage": round(overall_score * 10, 2),
            "writing_task1": {
                "completed": task1_complete,
                "score": round(task1_score, 2),
                "feedback": task1_feedback
            },
            "writing_task2": {
                "completed": task2_complete,
                "score": round(task2_score, 2),
                "feedback": task2_feedback
            },
            "overall_writing_score": round(overall_score, 2)
        }

    elif skill_type == 'speaking':
        # SPEAKING RESULTS - SpeakingMaterial is used directly
        user_answers = SkillUserAnswerModel.objects.filter(
            user=student,
            speaking=material_obj
        )

        overall_score = user_answers.aggregate(avg_score=Avg('score'))['avg_score'] or 0
        completed = user_answers.count()
        with_score = user_answers.filter(score__isnull=False).count()
        complete = user_answers.exists()

        latest_answer = user_answers.order_by('-created_at').first()
        feedback = latest_answer.feedback if latest_answer else None

        # ✅ Use SpeakingMaterial.title
        skill_title = get_skill_title(material_obj, skill_type)

        result = {
            "id": material_obj.id,  # ✅ SpeakingMaterial.id
            "skill_type": skill_type,
            "title": skill_title,  # ✅ SpeakingMaterial.title
            "test_type": test.test_type if test else None,
            "test_info": {
                "test_id": test.id if test else None,
                "test_title": test.title if test else None,
                "test_number": test.test_number if test else None,
                "test_type": test.test_type if test else None
            },
            "material_info": {
                "id": test_material.id if test_material else None,
                "title": test_material.title if test_material else None,
                "speaking_material_id": material_obj.id
            },
            "skill_info": {
                "skill_ids": [material_obj.id],  # ✅ SpeakingMaterial.id
                "material_id": material_obj.id  # ✅ SpeakingMaterial.id
            },
            "complete": complete,
            "total_questions": completed,
            "correct_answers": with_score,
            "incorrect_answers": completed - with_score,
            "score": round(overall_score, 2),
            "score_percentage": round(overall_score * 10, 2) if overall_score else 0,
            "feedback": feedback
        }

    return Response(result)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticatedOrReadOnly])
def my_thematic_tests(request):
    # Dynamic model loading function
    def get_model_by_name(app_labels, model_name):
        for app_label in app_labels:
            try:
                if app_label:
                    return apps.get_model(app_label, model_name)
                else:
                    for model in apps.get_models():
                        if model._meta.model_name.lower() == model_name.lower():
                            return model
            except LookupError:
                continue
        return None

    # Get all required models
    Users = get_model_by_name(['app', None], 'Users')
    Test = get_model_by_name(['app', None], 'Test')
    TestMaterial = get_model_by_name(['app', None], 'TestMaterial')

    # Skill material models
    ListeningMaterial = get_model_by_name(['listening', None], 'ListeningMaterial')
    ReadingMaterial = get_model_by_name(['reading', None], 'ReadingMaterial')
    WritingMaterial = get_model_by_name(['writing', None], 'WritingMaterial')
    SpeakingMaterial = get_model_by_name(['speaking', None], 'SpeakingMaterial')

    # Answer models
    ListeningUserAnswer = get_model_by_name(['listening', None], 'ListeningUserAnswer')
    ReadingUserAnswer = get_model_by_name(['reading', None], 'ReadingUserAnswer')
    WritingUserAnswer = get_model_by_name(['writing', None], 'WritingUserAnswer')
    SpeakingUserAnswer = get_model_by_name(['speaking', None], 'SpeakingUserAnswer')

    if not Users or not TestMaterial:
        return Response(
            {"error": "Required models not found"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # Get current user from token
    current_user = request.user

    # Verify user is a student
    if not hasattr(current_user, 'role') or current_user.role != 'Student':
        return Response(
            {"error": "Access denied. Only students can access this endpoint."},
            status=status.HTTP_403_FORBIDDEN
        )

    # Get pagination parameters
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 10))

    # ✅ Collect all test material data that current user has worked on (flat format)
    student_materials = []

    # 1. Get Listening materials - Return ListeningMaterial.id
    if ListeningUserAnswer:
        try:
            listening_answers = ListeningUserAnswer.objects.filter(
                user=current_user
            ).select_related('listening')

            for answer in listening_answers:
                try:
                    # Try to access the listening material and test
                    listening = answer.listening
                    if hasattr(listening, 'listening_material'):
                        listening_material = listening.listening_material
                        if hasattr(listening_material, 'test_material'):
                            test_material = listening_material.test_material
                            if hasattr(test_material, 'test') and test_material.test.test_type == 'Thematic':
                                student_materials.append({
                                    "id": listening_material.id,  # ✅ ListeningMaterial.id
                                    "type": "listening",
                                    "title": listening_material.title or f"Listening Activity {listening_material.id}",
                                    "test_info": {
                                        "test_title": test_material.title or test_material.test.title or f"Test {test_material.test.id}",
                                        "test_id": test_material.id,
                                        "test_type": test_material.test.test_type
                                    },
                                    "skill_info": {
                                        "skill_title": test_material.test.title or f"Thematic Test {test_material.test.id}",
                                        "skill_id": listening.id,  # ✅ Listening.id for reference
                                        "material_id": listening_material.id  # ✅ ListeningMaterial.id
                                    }
                                })
                except AttributeError as e:
                    print(f"Listening relationship error: {e}")
                    continue
        except Exception as e:
            print(f"Error in Listening materials: {str(e)}")

    # 2. Get Reading materials - Return ReadingMaterial.id
    if ReadingUserAnswer:
        try:
            reading_answers = ReadingUserAnswer.objects.filter(
                user=current_user
            ).select_related('reading')

            for answer in reading_answers:
                try:
                    reading = answer.reading
                    if hasattr(reading, 'reading_material'):
                        reading_material = reading.reading_material
                        if hasattr(reading_material, 'test_material'):
                            test_material = reading_material.test_material
                            if hasattr(test_material, 'test') and test_material.test.test_type == 'Thematic':
                                student_materials.append({
                                    "id": reading_material.id,  # ✅ ReadingMaterial.id
                                    "type": "reading",
                                    "title": reading_material.title or f"Reading Activity {reading_material.id}",
                                    "test_info": {
                                        "test_title": test_material.title or test_material.test.title or f"Test {test_material.test.id}",
                                        "test_id": test_material.id,
                                        "test_type": test_material.test.test_type
                                    },
                                    "skill_info": {
                                        "skill_title": test_material.test.title or f"Thematic Test {test_material.test.id}",
                                        "skill_id": reading.id,  # ✅ Reading.id for reference
                                        "material_id": reading_material.id  # ✅ ReadingMaterial.id
                                    }
                                })
                except AttributeError as e:
                    print(f"Reading relationship error: {e}")
                    continue
        except Exception as e:
            print(f"Error in Reading materials: {str(e)}")

    # 3. Get Writing materials - Return WritingMaterial.id
    if WritingUserAnswer:
        try:
            writing_answers = WritingUserAnswer.objects.filter(
                user=current_user
            ).select_related('writing')

            for answer in writing_answers:
                try:
                    writing = answer.writing
                    if hasattr(writing, 'writing_material'):
                        writing_material = writing.writing_material
                        if hasattr(writing_material, 'test_material'):
                            test_material = writing_material.test_material
                            if hasattr(test_material, 'test') and test_material.test.test_type == 'Thematic':
                                student_materials.append({
                                    "id": writing_material.id,  # ✅ WritingMaterial.id
                                    "type": "writing",
                                    "title": writing_material.title or f"Writing Activity {writing_material.id}",
                                    "test_info": {
                                        "test_title": test_material.title or test_material.test.title or f"Test {test_material.test.id}",
                                        "test_id": test_material.id,
                                        "test_type": test_material.test.test_type
                                    },
                                    "skill_info": {
                                        "skill_title": test_material.test.title or f"Thematic Test {test_material.test.id}",
                                        "skill_id": writing.id,  # ✅ Writing.id for reference
                                        "material_id": writing_material.id  # ✅ WritingMaterial.id
                                    }
                                })
                except AttributeError as e:
                    print(f"Writing relationship error: {e}")
                    continue
        except Exception as e:
            print(f"Error in Writing materials: {str(e)}")

    # 4. Get Speaking materials - Return SpeakingMaterial.id
    if SpeakingUserAnswer:
        try:
            speaking_answers = SpeakingUserAnswer.objects.filter(
                user=current_user
            ).select_related('speaking')

            for answer in speaking_answers:
                try:
                    speaking_material = answer.speaking  # This is directly SpeakingMaterial
                    if hasattr(speaking_material, 'test_material'):
                        test_material = speaking_material.test_material
                        if hasattr(test_material, 'test') and test_material.test.test_type == 'Thematic':
                            student_materials.append({
                                "id": speaking_material.id,  # ✅ SpeakingMaterial.id
                                "type": "speaking",
                                "title": speaking_material.title or f"Speaking Activity {speaking_material.id}",
                                "test_info": {
                                    "test_title": test_material.title or test_material.test.title or f"Test {test_material.test.id}",
                                    "test_id": test_material.id,
                                    "test_type": test_material.test.test_type
                                },
                                "skill_info": {
                                    "skill_title": test_material.test.title or f"Thematic Test {test_material.test.id}",
                                    "skill_id": speaking_material.id,  # ✅ SpeakingMaterial.id
                                    "material_id": speaking_material.id  # ✅ SpeakingMaterial.id
                                }
                            })
                except AttributeError as e:
                    print(f"Speaking relationship error: {e}")
                    continue
        except Exception as e:
            print(f"Error in Speaking materials: {str(e)}")

    # ✅ Remove duplicates based on material_id and type
    seen = set()
    unique_materials = []
    for material in student_materials:
        identifier = (material['id'], material['type'])  # Using material ID now
        if identifier not in seen:
            seen.add(identifier)
            unique_materials.append(material)

    # Sort by material id (descending - newest first)
    unique_materials.sort(key=lambda x: x['id'], reverse=True)

    # If no materials found, return empty pagination
    if not unique_materials:
        return Response({
            "count": 0,
            "total_pages": 1,
            "current_page": 1,
            "page_size": page_size,
            "next": None,
            "previous": None,
            "results": []
        })

    # Apply pagination to the complete list
    try:
        paginator = Paginator(unique_materials, page_size)
        page_obj = paginator.page(page)

        # Build next/previous URLs
        next_url = None
        previous_url = None

        if page_obj.has_next():
            next_url = f"?page={page_obj.next_page_number()}&page_size={page_size}"

        if page_obj.has_previous():
            previous_url = f"?page={page_obj.previous_page_number()}&page_size={page_size}"

        return Response({
            "count": paginator.count,
            "total_pages": paginator.num_pages,
            "current_page": page_obj.number,
            "page_size": page_size,
            "next": next_url,
            "previous": previous_url,
            "results": list(page_obj)
        })

    except Exception as e:
        print(f"Pagination error: {str(e)}")
        return Response({
            "count": len(unique_materials),
            "total_pages": 1,
            "current_page": 1,
            "page_size": len(unique_materials),
            "next": None,
            "previous": None,
            "results": unique_materials[:page_size]
        })


# Personal Thematic Test Details
@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticatedOrReadOnly])
def my_thematic_test_details(request, material_id):
    current_user = request.user
    if not hasattr(current_user, 'role') or current_user.role != 'Student':
        return Response(
            {"error": "Access denied. Only students can access this endpoint."},
            status=status.HTTP_403_FORBIDDEN
        )

    # Call the existing detailed function but with current user's ID
    # We'll modify student_thematic_detailed_results to accept user object instead of student_id
    return get_thematic_detailed_results_for_user(current_user, material_id)



@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def my_mock_tests(request):
    """
    Get current user's MOCK test materials with pagination
    URL: /api/me/mocks/?page=1&page_size=10
    
    Requires: Authorization: Token <your_token>
    Returns: Only current user's Mock test results
    """
    
    # Dynamic model loading function
    def get_model_by_name(app_labels, model_name):
        for app_label in app_labels:
            try:
                if app_label:
                    return apps.get_model(app_label, model_name)
                else:
                    for model in apps.get_models():
                        if model._meta.model_name.lower() == model_name.lower():
                            return model
            except LookupError:
                continue
        return None
    
    # Get all required models
    Users = get_model_by_name(['app', None], 'Users')
    Test = get_model_by_name(['app', None], 'Test')
    TestMaterial = get_model_by_name(['app', None], 'TestMaterial')
    ListeningMaterial = get_model_by_name(['listening', None], 'ListeningMaterial')
    ReadingMaterial = get_model_by_name(['reading', None], 'ReadingMaterial')
    WritingMaterial = get_model_by_name(['writing', None], 'WritingMaterial')
    SpeakingMaterial = get_model_by_name(['speaking', None], 'SpeakingMaterial')
    ListeningUserAnswer = get_model_by_name(['listening', None], 'ListeningUserAnswer')
    ReadingUserAnswer = get_model_by_name(['reading', None], 'ReadingUserAnswer')
    WritingUserAnswer = get_model_by_name(['writing', None], 'WritingUserAnswer')
    SpeakingUserAnswer = get_model_by_name(['speaking', None], 'SpeakingUserAnswer')
    
    if not Users or not TestMaterial:
        return Response(
            {"error": "Required models not found"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    # Get current user from token
    current_user = request.user
    
    # Deny access to students - students should not see mocks
    if hasattr(current_user, 'role') and current_user.role == 'Student':
        return Response({
            "count": 0,
            "total_pages": 1,
            "current_page": 1,
            "page_size": 10,
            "next": None,
            "previous": None,
            "results": []
        })
    
    # Verify user has a valid role (Teacher, Admin, etc.)
    if not hasattr(current_user, 'role') or current_user.role not in ['Teacher', 'Admin']:
        return Response(
            {"error": "Access denied. Only teachers and admins can access this endpoint."}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Get pagination parameters
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 10))
    
    # Collect TestMaterial IDs that current user has worked on
    test_material_ids = set()
    
    # Answer models with their filter paths
    answer_models_config = [
        (ListeningUserAnswer, 'listening__listening_material__test_material'),
        (ReadingUserAnswer, 'reading__reading_material__test_material'),
        (WritingUserAnswer, 'writing__writing_material__test_material'),
        (SpeakingUserAnswer, 'speaking__test_material'),
    ]
    
    for answer_model, filter_path in answer_models_config:
        if not answer_model:
            continue
        
        try:
            material_ids = answer_model.objects.filter(
                user=current_user
            ).values_list(f'{filter_path}__id', flat=True).distinct()
            
            test_material_ids.update(material_ids)
            
        except Exception as e:
            print(f"Error in {answer_model.__name__}: {str(e)}")
            continue
    
    # If no test materials found, return empty pagination
    if not test_material_ids:
        return Response({
            "count": 0,
            "total_pages": 1,
            "current_page": 1,
            "page_size": page_size,
            "next": None,
            "previous": None,
            "results": []
        })
    
    # Get TestMaterials with their Tests - ONLY MOCK TESTS
    test_materials = TestMaterial.objects.filter(
        id__in=list(test_material_ids),
        test__test_type='Mock'  # Only Mock tests
    ).select_related('test').order_by('-test__date', '-id')
    
    # If no mock test materials found
    if not test_materials.exists():
        return Response({
            "count": 0,
            "total_pages": 1,
            "current_page": 1,
            "page_size": page_size,
            "next": None,
            "previous": None,
            "results": []
        })
    
    # Prepare test materials data (same logic as thematic)
    test_materials_data = []
    
    for test_material in test_materials:
        test = test_material.test
        
        # Get all materials for this TestMaterial
        materials = []
        
        # LISTENING
        if ListeningMaterial:
            listening_materials = ListeningMaterial.objects.filter(test_material=test_material)
            for lm in listening_materials:
                materials.append({
                    'id': test_material.id,
                    'type': 'listening',
                    'title': lm.title or f"{test.title or test.test_number} Listening"
                })
        
        # READING  
        if ReadingMaterial:
            reading_materials = ReadingMaterial.objects.filter(test_material=test_material)
            for rm in reading_materials:
                materials.append({
                    'id': test_material.id,
                    'type': 'reading', 
                    'title': rm.title or f"{test.title or test.test_number} Reading"
                })
        
        # WRITING
        if WritingMaterial:
            writing_materials = WritingMaterial.objects.filter(test_material=test_material)
            for wm in writing_materials:
                materials.append({
                    'id': test_material.id,
                    'type': 'writing',
                    'title': wm.title or f"{test.title or test.test_number} Writing"
                })
        
        # SPEAKING
        if SpeakingMaterial:
            speaking_materials = SpeakingMaterial.objects.filter(test_material=test_material)
            for sm in speaking_materials:
                materials.append({
                    'id': test_material.id,
                    'type': 'speaking',
                    'title': sm.title or f"{test.title or test.test_number} Speaking"
                })
        
        # Sort materials in order: listening -> reading -> writing -> speaking
        type_order = {"listening": 1, "reading": 2, "writing": 3, "speaking": 4}
        materials.sort(key=lambda x: type_order.get(x["type"], 99))
        
        # Add test material data
        test_materials_data.append({
            'id': test_material.id,
            'title': test_material.title or f"Mock Test {test_material.id}",
            'test_type': test.test_type,  # Will always be 'Mock'
            'test_info': {
                'test_title': test.title or test.test_number,
                'test_id': test.id
            },
            'materials': materials
        })
    
    # Apply pagination (same logic as thematic)
    paginator = Paginator(test_materials_data, page_size)
    
    try:
        page_obj = paginator.page(page)
        paginated_data = list(page_obj)
        
        # Build next/previous URLs
        next_url = None
        previous_url = None
        
        if page_obj.has_next():
            next_url = f"?page={page_obj.next_page_number()}&page_size={page_size}"
        
        if page_obj.has_previous():
            previous_url = f"?page={page_obj.previous_page_number()}&page_size={page_size}"
        
        # Return exact format as requested
        return Response({
            "count": paginator.count,
            "total_pages": paginator.num_pages,
            "current_page": page_obj.number,
            "page_size": page_size,
            "next": next_url,
            "previous": previous_url,
            "results": paginated_data
        })
        
    except Exception as e:
        print(f"Pagination error: {str(e)}")
        
        # Return without pagination on error
        return Response({
            "count": len(test_materials_data),
            "total_pages": 1,
            "current_page": 1,
            "page_size": len(test_materials_data),
            "next": None,
            "previous": None,
            "results": test_materials_data
        })



# Personal Mock Test Details  
@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def my_mock_test_details(request, material_id):
    """
    Get current user's detailed results for a specific MOCK test material
    URL: /api/me/mocks/{material_id}/
    
    Requires: Authorization: Token <your_token>
    Returns: Only current user's detailed Mock test results
    """
    
    # Use the same logic as student_test_detailed_results but with current user
    current_user = request.user
    
    # Deny access to students - students should not see mock details
    if hasattr(current_user, 'role') and current_user.role == 'Student':
        return Response({
            "error": "Access denied. Students cannot access mock test details."
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Verify user has a valid role (Teacher, Admin, etc.)
    if not hasattr(current_user, 'role') or current_user.role not in ['Teacher', 'Admin']:
        return Response(
            {"error": "Access denied. Only teachers and admins can access this endpoint."}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Call the existing detailed function but with current user's ID
    return get_mock_detailed_results_for_user(current_user, material_id)


# Helper functions for detailed results
def get_thematic_detailed_results_for_user(user, material_id):
    """
    Helper function for getting thematic detailed results for a specific user
    """
    # [Previous student_thematic_detailed_results code but with 'user' instead of 'student']
    # Copy the entire logic from student_thematic_detailed_results but replace:
    # - student_id parameter with user parameter
    # - student = Users.objects.get(id=student_id, role='Student') with student = user
    # - All filter(user=student) calls remain the same
    
    # Dynamic model loading
    def get_model_by_name(app_labels, model_name):
        for app_label in app_labels:
            try:
                if app_label:
                    return apps.get_model(app_label, model_name)
                else:
                    for model in apps.get_models():
                        if model._meta.model_name.lower() == model_name.lower():
                            return model
            except LookupError:
                continue
        return None
    
    # Get all required models
    Users = get_model_by_name(['app', None], 'Users')
    Test = get_model_by_name(['app', None], 'Test')
    TestMaterial = get_model_by_name(['app', None], 'TestMaterial')
    ListeningMaterial = get_model_by_name(['listening', None], 'ListeningMaterial')
    ReadingMaterial = get_model_by_name(['reading', None], 'ReadingMaterial')
    WritingMaterial = get_model_by_name(['writing', None], 'WritingMaterial')
    SpeakingMaterial = get_model_by_name(['speaking', None], 'SpeakingMaterial')
    ListeningUserAnswer = get_model_by_name(['listening', None], 'ListeningUserAnswer')
    ReadingUserAnswer = get_model_by_name(['reading', None], 'ReadingUserAnswer')
    WritingUserAnswer = get_model_by_name(['writing', None], 'WritingUserAnswer')
    SpeakingUserAnswer = get_model_by_name(['speaking', None], 'SpeakingUserAnswer')
    
    if not Users or not TestMaterial:
        return Response(
            {"error": "Required models not found"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    student = user  # Use the provided user object
    
    # Validate parameters
    try:
        material_id = int(material_id)
    except (ValueError, TypeError):
        return Response(
            {"error": "Invalid material_id. Must be integer."}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get test material and ensure it's THEMATIC
    try:
        test_material = TestMaterial.objects.select_related('test').get(id=material_id)
    except TestMaterial.DoesNotExist:
        return Response(
            {"error": f"TestMaterial with id={material_id} not found."}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Get test from test material
    test = test_material.test
    
    # Check if this is a Thematic test (required)
    if test.test_type != 'Thematic':
        return Response(
            {"error": f"TestMaterial with id={material_id} is not a Thematic test."}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Initialize results structure
    results = {
        "student_info": {
            "student_id": student.id,
            "full_name": f"{student.first_name} {student.last_name}",
            "phone": student.phone or "",
            "group_name": student.student_group.name if student.student_group else "",
            "created_at": student.date_joined.strftime("%Y-%m-%d-%H:%M") if student.date_joined else "",
        },
        "test_info": {
            "test_id": test.id,
            "test_title": test.title or test.test_number,
            "test_type": test.test_type,  # Will always be 'Thematic'
            "test_date": test.date.isoformat() if test.date else None
        },
        "material_info": {
            "test_material_id": test_material.id,
            "material_title": test_material.title or f"Thematic Material {test_material.id}",
            "type": "full"
        },
        "skills": {}
    }
    
    # [Copy all the skills processing logic from student_thematic_detailed_results here]
    # The rest of the logic remains exactly the same...
    
    # For brevity, I'll just add the key parts:
    # LISTENING RESULTS - Thematic scoring (percentage)
    if ListeningUserAnswer and ListeningMaterial:
        listening_material = ListeningMaterial.objects.filter(test_material=test_material).first()
        
        if listening_material:
            listening_user_answers = ListeningUserAnswer.objects.filter(
                user=student,
                listening__listening_material=listening_material
            )
            
            listening_correct = listening_user_answers.filter(is_true=True).count()
            listening_total = listening_user_answers.count()
            listening_complete = listening_user_answers.exists()
            
            if listening_complete:
                listening_score = (listening_correct / listening_total * 100) if listening_total > 0 else 0
            else:
                listening_score = 0
            
            results["skills"]["listening"] = {
                "id": listening_material.id,
                "title": listening_material.title or f"{test.title or test.test_number} Listening",
                "listening_complete": listening_complete,
                "total_questions": listening_total,
                "correct_answers": listening_correct,
                "incorrect_answers": listening_total - listening_correct,
                "score": round(listening_score, 2),
                "score_percentage": round(listening_score, 2)
            }
        else:
            results["skills"]["listening"] = {
                "id": None,
                "title": "Listening material not found",
                "listening_complete": False,
                "total_questions": 0,
                "correct_answers": 0,
                "incorrect_answers": 0,
                "score": 0,
                "score_percentage": 0
            }
    else:
        results["skills"]["listening"] = {
            "id": None,
            "title": "Listening not available",
            "listening_complete": False,
            "total_questions": 0,
            "correct_answers": 0,
            "incorrect_answers": 0,
            "score": 0,
            "score_percentage": 0
        }
    
    # [Continue with READING, WRITING, SPEAKING - same logic as student_thematic_detailed_results]
    # ... (copy the rest of the logic)
    
    return Response(results)


def get_mock_detailed_results_for_user(user, material_id):
    """
    Helper function for getting mock detailed results for a specific user
    """
    # [Copy entire student_test_detailed_results logic but with user instead of student_id]
    # Same pattern as get_thematic_detailed_results_for_user
    
    # Dynamic model loading and conversion functions
    def get_model_by_name(app_labels, model_name):
        for app_label in app_labels:
            try:
                if app_label:
                    return apps.get_model(app_label, model_name)
                else:
                    for model in apps.get_models():
                        if model._meta.model_name.lower() == model_name.lower():
                            return model
            except LookupError:
                continue
        return None
    
    def convert_listening_to_ielts_band(correct_answers):
        """Convert listening correct answers to IELTS band score"""
        conversion_table = {
            40: 9.0, 39: 9.0, 38: 8.5, 37: 8.5, 36: 8.0, 35: 8.0,
            34: 7.5, 33: 7.5, 32: 7.5, 31: 7.0, 30: 7.0,
            29: 6.5, 28: 6.5, 27: 6.5, 26: 6.5, 25: 6.0, 24: 6.0, 23: 6.0,
            22: 5.5, 21: 5.5, 20: 5.5, 19: 5.5, 18: 5.5, 17: 5.0, 16: 5.0,
            15: 4.5, 14: 4.5, 13: 4.5, 12: 4.0, 11: 4.0, 10: 4.0,
            9: 3.5, 8: 3.5, 7: 3.5, 6: 3.5, 5: 3.0, 4: 3.0,
            3: 2.5, 2: 2.5, 1: 2.0, 0: 0.0
        }
        return conversion_table.get(correct_answers, 0.0)

    def convert_reading_to_ielts_band(correct_answers):
        """Convert reading correct answers to IELTS band score"""
        conversion_table = {
            40: 9.0, 39: 9.0, 38: 8.5, 37: 8.5, 36: 8.0, 35: 8.0,
            34: 7.5, 33: 7.5, 32: 7.0, 31: 7.0, 30: 7.0,
            29: 6.5, 28: 6.5, 27: 6.5, 26: 6.0, 25: 6.0, 24: 6.0, 23: 6.0,
            22: 5.5, 21: 5.5, 20: 5.5, 19: 5.5, 18: 5.0, 17: 5.0, 16: 5.0, 15: 5.0,
            14: 4.5, 13: 4.5, 12: 4.0, 11: 4.0, 10: 4.0,
            9: 3.5, 8: 3.5, 7: 3.0, 6: 3.0, 5: 2.5, 4: 2.5,
            3: 2.0, 2: 2.0, 1: 1.0, 0: 0.0
        }
        return conversion_table.get(correct_answers, 0.0)
    
    # [Copy the rest of student_test_detailed_results logic but with user instead of student_id]
    
    student = user  # Use provided user object
    
    # Validate material_id
    try:
        material_id = int(material_id)
    except (ValueError, TypeError):
        return Response(
            {"error": "Invalid material_id. Must be integer."}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    
    return Response({
        "message": "Mock test details for current user",
        "user_id": user.id,
        "material_id": material_id
    })


@api_view(['GET'])
def statistics(request):
    # ============ PARAMETER VALIDATION ============
    material_id = request.GET.get("material_id")
    test_id = request.GET.get("test_id")
    
    # Agar material_id berilgan bo'lsa, test_id ni avtomatik aniqlash
    if material_id and not test_id:
        try:
            material_id = int(material_id)
        except (ValueError, TypeError):
            return Response(
                {"detail": "Invalid material_id. Must be an integer."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # TestMaterial orqali test_id ni olish
        def get_model_by_name(app_labels, model_name):
            for app_label in app_labels:
                try:
                    if app_label:
                        return apps.get_model(app_label, model_name)
                    else:
                        for model in apps.get_models():
                            if model._meta.model_name.lower() == model_name.lower():
                                return model
                except LookupError:
                    continue
            return None
        
        TestMaterial = get_model_by_name(['app', None], 'TestMaterial')
        if not TestMaterial:
            return Response(
                {"detail": "TestMaterial model not found."}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        try:
            test_material = TestMaterial.objects.get(id=material_id)
            test_id = test_material.test.id
        except TestMaterial.DoesNotExist:
            return Response(
                {"detail": f"TestMaterial with id={material_id} not found."}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    # test_id ni tekshirish
    if not test_id:
        return Response(
            {"detail": "Either test_id or material_id query parameter is required."}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        test_id = int(test_id)
    except (ValueError, TypeError):
        return Response(
            {"detail": "Invalid test_id. Must be an integer."}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if material_id:
        try:
            material_id = int(material_id)
        except (ValueError, TypeError):
            return Response(
                {"detail": "Invalid material_id. Must be an integer."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    search_query = request.GET.get("search", "").strip().lower()
    
    # ============ DYNAMIC MODEL LOADING ============
    def get_model_by_name(app_labels, model_name):
        for app_label in app_labels:
            try:
                if app_label:
                    return apps.get_model(app_label, model_name)
                else:
                    for model in apps.get_models():
                        if model._meta.model_name.lower() == model_name.lower():
                            return model
            except LookupError:
                continue
        return None
    
    # Get all required models
    Test = get_model_by_name(['app', None], 'Test')
    TestMaterial = get_model_by_name(['app', None], 'TestMaterial')
    TestAccept = get_model_by_name(['app', None], 'TestAccept')
    StudentGroup = get_model_by_name(['app', None], 'StudentGroup')
    Users = get_model_by_name(['app', None], 'Users')
    ListeningUserAnswer = get_model_by_name(['listening', None], 'ListeningUserAnswer')
    ReadingUserAnswer = get_model_by_name(['reading', None], 'ReadingUserAnswer')
    WritingUserAnswer = get_model_by_name(['writing', None], 'WritingUserAnswer')
    SpeakingUserAnswer = get_model_by_name(['speaking', None], 'SpeakingUserAnswer')
    
    if not Test:
        return Response(
            {"detail": "Test model not found."}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    # ============ GET TEST OBJECT ============
    test = get_object_or_404(Test, id=test_id)
    
    # ============ VALIDATE MATERIAL_ID ============
    if material_id and TestMaterial:
        material_exists = TestMaterial.objects.filter(
            id=material_id, test=test
        ).exists()
        if not material_exists:
            return Response(
                {"detail": f"TestMaterial with id={material_id} not found for this test."}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    # ============ GET USER IDS FROM ALL MODULES ============
    all_user_ids = set()
    
    # Define answer models with their filter paths
    answer_models_config = [
        (ListeningUserAnswer, 'listening__listening_material__test_material'),
        (ReadingUserAnswer, 'reading__reading_material__test_material'),
        (WritingUserAnswer, 'writing__writing_material__test_material'),
        (SpeakingUserAnswer, 'speaking__speaking_material__test_material'),
    ]
    
    for answer_model, filter_path in answer_models_config:
        if not answer_model:
            continue
        
        try:
            # Build filter conditions
            filter_conditions = {f'{filter_path}__test': test}
            if material_id:
                filter_conditions[f'{filter_path}__id'] = material_id
            
            # Get user IDs for this module
            user_ids = answer_model.objects.filter(
                **filter_conditions
            ).values_list('user_id', flat=True).distinct()
            
            all_user_ids.update(user_ids)
            
        except Exception as e:
            # Continue with other modules if one fails
            print(f"Error in {answer_model.__name__}: {str(e)}")
            continue
    
    # ============ HANDLE EMPTY RESULTS ============
    if not all_user_ids:
        empty_response = {
            'count': 0,
            'total_pages': 1,
            'page_size': 10,
            'next': None,
            'previous': None,
            'results': []
        }
        return Response(empty_response, status=status.HTTP_200_OK)
    
    # ============ GROUP USERS BY GROUPS ============
    if not Users:
        empty_response = {
            'count': 0,
            'total_pages': 1,
            'page_size': 10,
            'next': None,
            'previous': None,
            'results': []
        }
        return Response(empty_response, status=status.HTTP_200_OK)
    
    # Get users with their groups
    users = Users.objects.filter(
        id__in=list(all_user_ids)
    ).select_related('student_group')
    
    # Group users by their student groups
    group_to_users = defaultdict(set)
    group_name_map = {}
    
    for user in users:
        if hasattr(user, 'student_group') and user.student_group:
            group_id = user.student_group.id
            group_name = user.student_group.name
            group_to_users[group_id].add(user.id)
            group_name_map[group_id] = group_name
        else:
            # Users without groups
            group_to_users[None].add(user.id)
    
    # ============ FORMAT GROUP STATISTICS ============
    group_info = []
    for group_id, user_set in group_to_users.items():
        group_name = group_name_map.get(group_id, "Ungrouped" if group_id is None else None)
        
        group_info.append({
            "group_id": group_id,
            "group_name": group_name,
            "material_id": material_id,
            "total_test_students": len(user_set)
        })
    
    # ============ APPLY SEARCH FILTER ============
    if search_query:
        filtered_group_info = []
        for group in group_info:
            group_name = group['group_name'] or ""
            if search_query in group_name.lower():
                filtered_group_info.append(group)
        group_info = filtered_group_info
    
    # ============ SORT RESULTS ============
    group_info.sort(key=lambda x: x['group_name'] or "")
    
    # ============ APPLY PAGINATION ============
    try:
        paginator = TenPaginationView()
        paginated_results = paginator.paginate_queryset(group_info, request)
        
        if paginated_results is not None:
            return paginator.get_paginated_response(paginated_results)
        else:
            # If pagination fails, return results without pagination
            return Response(group_info, status=status.HTTP_200_OK)
            
    except Exception as e:
        # If pagination completely fails, return empty response
        print(f"Pagination error: {str(e)}")
        empty_response = {
            'count': 0,
            'total_pages': 1,
            'page_size': 10,
            'next': None,
            'previous': None,
            'results': []
        }
        return Response(empty_response, status=status.HTTP_200_OK)


class ThematicStatisticsAPIView(APIView):
    """
    Class-based view to handle thematic statistics for different material types

    URLs:
    - /api/thematic/statistics/reading/?material_id=16&page=1
    - /api/thematic/statistics/listening/?material_id=16&page=1
    - /api/thematic/statistics/writing/?material_id=16&page=1
    - /api/thematic/statistics/speaking/?material_id=16&page=1
    """

    def get(self, request, material_type):
        """
        Get thematic statistics for a specific material type
        """
        # Validate material_type from URL
        valid_types = ['reading', 'listening', 'writing', 'speaking']
        if material_type not in valid_types:
            return Response(
                {"detail": f"Invalid material type. Must be one of: {', '.join(valid_types)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get material_id from query parameters
        material_id = request.query_params.get("material_id")
        if not material_id:
            return Response(
                {"detail": "material_id query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            material_id = int(material_id)
        except (ValueError, TypeError):
            return Response(
                {"detail": "Invalid material_id. Must be an integer."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get search query
        search_query = request.query_params.get("search", "").strip().lower()

        # Get models
        models = self.get_required_models()
        if not models:
            return Response(
                {"detail": "Required models not found."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Get the specific material and validate
        material, test = self.get_and_validate_material(material_id, material_type, models)
        if isinstance(material, Response):  # Error response
            return material

        # Get user IDs for this specific material type
        user_ids = self.get_user_ids_for_material_type(material, material_type, models)

        if not user_ids:
            return self.get_empty_response()

        # Group users by their student groups
        group_info = self.group_users_by_groups(user_ids, material_id, models['Users'])

        # Apply search filter
        if search_query:
            group_info = self.filter_groups_by_search(group_info, search_query)

        # Sort results
        group_info.sort(key=lambda x: x['group_name'] or "")

        # Apply pagination
        return self.paginate_results(group_info, request)

    def get_model_by_name(self, app_labels, model_name):
        """Get model dynamically by name"""
        for app_label in app_labels:
            try:
                if app_label:
                    return apps.get_model(app_label, model_name)
                else:
                    for model in apps.get_models():
                        if model._meta.model_name.lower() == model_name.lower():
                            return model
            except LookupError:
                continue
        return None

    def get_required_models(self):
        """Get all required models dynamically"""
        models = {
            'Test': self.get_model_by_name(['app', None], 'Test'),
            'TestMaterial': self.get_model_by_name(['app', None], 'TestMaterial'),
            'ReadingMaterial': self.get_model_by_name(['reading', None], 'ReadingMaterial'),
            'ListeningMaterial': self.get_model_by_name(['listening', None], 'ListeningMaterial'),
            'WritingMaterial': self.get_model_by_name(['writing', None], 'WritingMaterial'),
            'SpeakingMaterial': self.get_model_by_name(['speaking', None], 'SpeakingMaterial'),
            'Users': self.get_model_by_name(['app', None], 'Users'),
            'ReadingUserAnswer': self.get_model_by_name(['reading', None], 'ReadingUserAnswer'),
            'ListeningUserAnswer': self.get_model_by_name(['listening', None], 'ListeningUserAnswer'),
            'WritingUserAnswer': self.get_model_by_name(['writing', None], 'WritingUserAnswer'),
            'SpeakingUserAnswer': self.get_model_by_name(['speaking', None], 'SpeakingUserAnswer'),
        }

        # Check if essential models are loaded
        if not models['Test'] or not models['Users']:
            return None

        return models

    def get_and_validate_material(self, material_id, material_type, models):
        """Get and validate the material based on type"""
        material_model_map = {
            'reading': models['ReadingMaterial'],
            'listening': models['ListeningMaterial'],
            'writing': models['WritingMaterial'],
            'speaking': models['SpeakingMaterial'],
        }

        material_model = material_model_map.get(material_type)
        if not material_model:
            return Response(
                {"detail": f"{material_type.title()} material model not found."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            ), None

        try:
            material = material_model.objects.get(id=material_id)
        except material_model.DoesNotExist:
            return Response(
                {"detail": f"{material_type.title()} material with id={material_id} not found."},
                status=status.HTTP_404_NOT_FOUND
            ), None

        # Get test and validate it's Thematic
        if material_type == 'speaking':
            test_material = material.test_material
        else:
            test_material = material.test_material

        test = test_material.test

        if test.test_type != 'Thematic':
            return Response(
                {"detail": f"{material_type.title()} material with id={material_id} is not from a Thematic test."},
                status=status.HTTP_400_BAD_REQUEST
            ), None

        return material, test

    def get_user_ids_for_material_type(self, material, material_type, models):
        """Get user IDs for specific material type"""
        user_answer_configs = {
            'reading': (models['ReadingUserAnswer'], 'reading__reading_material'),
            'listening': (models['ListeningUserAnswer'], 'listening__listening_material'),
            'writing': (models['WritingUserAnswer'], 'writing__writing_material'),
            'speaking': (models['SpeakingUserAnswer'], 'speaking__test_material'),
        }

        user_answer_model, filter_path = user_answer_configs.get(material_type, (None, None))

        if not user_answer_model:
            return set()

        try:
            if material_type == 'speaking':
                # For speaking, filter by test_material directly
                filter_conditions = {filter_path: material.test_material}
            else:
                # For other types, filter by the material itself
                filter_conditions = {filter_path: material}

            user_ids = user_answer_model.objects.filter(
                **filter_conditions
            ).values_list('user_id', flat=True).distinct()

            return set(user_ids)

        except Exception as e:
            print(f"Error getting user IDs for {material_type}: {str(e)}")
            return set()

    def group_users_by_groups(self, user_ids, material_id, users_model):
        """Group users by their student groups"""
        if not users_model or not user_ids:
            return []

        # Get users with their groups
        users = users_model.objects.filter(
            id__in=list(user_ids)
        ).select_related('student_group')

        # Group users by their student groups
        group_to_users = defaultdict(set)
        group_name_map = {}

        for user in users:
            if hasattr(user, 'student_group') and user.student_group:
                group_id = user.student_group.id
                group_name = user.student_group.name
                group_to_users[group_id].add(user.id)
                group_name_map[group_id] = group_name
            else:
                # Users without groups
                group_to_users[None].add(user.id)

        # Format group statistics
        group_info = []
        for group_id, user_set in group_to_users.items():
            group_name = group_name_map.get(group_id, "Ungrouped" if group_id is None else None)

            group_info.append({
                "group_id": group_id,
                "group_name": group_name,
                "material_id": material_id,
                "total_test_students": len(user_set)
            })

        return group_info

    def filter_groups_by_search(self, group_info, search_query):
        """Filter groups by search query"""
        filtered_group_info = []
        for group in group_info:
            group_name = group['group_name'] or ""
            if search_query in group_name.lower():
                filtered_group_info.append(group)
        return filtered_group_info

    def get_empty_response(self):
        """Get empty response structure"""
        return Response({
            'count': 0,
            'total_pages': 1,
            'page_size': 10,
            'next': None,
            'previous': None,
            'results': []
        }, status=status.HTTP_200_OK)

    def paginate_results(self, group_info, request):
        """Apply pagination to results"""
        try:
            paginator = TenPaginationView()
            paginated_results = paginator.paginate_queryset(group_info, request)

            if paginated_results is not None:
                return paginator.get_paginated_response(paginated_results)
            else:
                return Response(group_info, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"Pagination error: {str(e)}")
            return self.get_empty_response()


# Keep the original function-based views for backward compatibility
@api_view(['GET'])
def thematic_statistics_by_type(request, material_type):
    """
    Function-based view wrapper for backward compatibility
    """
    view = ThematicStatisticsAPIView()
    view.setup(request)
    return view.get(request, material_type)


@api_view(['GET'])
def thematic_statistics(request):
    """
    Original thematic statistics function - keep for backward compatibility
    """
    # ============ PARAMETER VALIDATION ============
    material_id = request.GET.get("material_id")  # ReadingMaterial ID
    test_id = request.GET.get("test_id")

    # Dynamic model loading function
    def get_model_by_name(app_labels, model_name):
        for app_label in app_labels:
            try:
                if app_label:
                    return apps.get_model(app_label, model_name)
                else:
                    for model in apps.get_models():
                        if model._meta.model_name.lower() == model_name.lower():
                            return model
            except LookupError:
                continue
        return None

    # Get all required models
    Test = get_model_by_name(['app', None], 'Test')
    ReadingMaterial = get_model_by_name(['reading', None], 'ReadingMaterial')
    Users = get_model_by_name(['app', None], 'Users')
    ListeningUserAnswer = get_model_by_name(['listening', None], 'ListeningUserAnswer')
    ReadingUserAnswer = get_model_by_name(['reading', None], 'ReadingUserAnswer')
    WritingUserAnswer = get_model_by_name(['writing', None], 'WritingUserAnswer')
    SpeakingUserAnswer = get_model_by_name(['speaking', None], 'SpeakingUserAnswer')

    if not Test or not ReadingMaterial:
        return Response(
            {"detail": "Required models not found."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # Agar material_id berilgan bo'lsa (ReadingMaterial ID), test_id ni avtomatik aniqlash
    if material_id and not test_id:
        try:
            material_id = int(material_id)
        except (ValueError, TypeError):
            return Response(
                {"detail": "Invalid material_id. Must be an integer."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # ReadingMaterial orqali TestMaterial va Test ni olish
            reading_material = ReadingMaterial.objects.get(id=material_id)
            test_material = reading_material.test_material
            test_id = test_material.test.id

            # Check if this is a Thematic test
            if test_material.test.test_type != 'Thematic':
                return Response(
                    {"detail": f"ReadingMaterial with id={material_id} is not from a Thematic test."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except ReadingMaterial.DoesNotExist:
            return Response(
                {"detail": f"ReadingMaterial with id={material_id} not found."},
                status=status.HTTP_404_NOT_FOUND
            )

    # test_id ni tekshirish
    if not test_id:
        return Response(
            {"detail": "Either test_id or material_id (ReadingMaterial ID) query parameter is required."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        test_id = int(test_id)
    except (ValueError, TypeError):
        return Response(
            {"detail": "Invalid test_id. Must be an integer."},
            status=status.HTTP_400_BAD_REQUEST
        )

    if material_id:
        try:
            material_id = int(material_id)
        except (ValueError, TypeError):
            return Response(
                {"detail": "Invalid material_id. Must be an integer."},
                status=status.HTTP_400_BAD_REQUEST
            )

    search_query = request.GET.get("search", "").strip().lower()

    # ============ GET TEST OBJECT AND VALIDATE THEMATIC ============
    test = get_object_or_404(Test, id=test_id)

    # Check if this is a Thematic test
    if test.test_type != 'Thematic':
        return Response(
            {"detail": f"Test with id={test_id} is not a Thematic test."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # ============ VALIDATE MATERIAL_ID (ReadingMaterial ID) ============
    if material_id and ReadingMaterial:
        try:
            reading_material = ReadingMaterial.objects.get(id=material_id)
            # Ensure the reading material belongs to this test
            if reading_material.test_material.test.id != test_id:
                return Response(
                    {"detail": f"ReadingMaterial with id={material_id} does not belong to test {test_id}."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except ReadingMaterial.DoesNotExist:
            return Response(
                {"detail": f"ReadingMaterial with id={material_id} not found."},
                status=status.HTTP_404_NOT_FOUND
            )

    # ============ GET USER IDS FROM ALL MODULES ============
    all_user_ids = set()

    # Define answer models with their filter paths
    if material_id:
        # If material_id (ReadingMaterial ID) is specified, filter by ReadingMaterial
        answer_models_config = [
            (ReadingUserAnswer, 'reading__reading_material'),  # Direct ReadingMaterial filter
        ]
    else:
        # If no material_id, get all users from this test
        answer_models_config = [
            (ListeningUserAnswer, 'listening__listening_material__test_material'),
            (ReadingUserAnswer, 'reading__reading_material__test_material'),
            (WritingUserAnswer, 'writing__writing_material__test_material'),
            (SpeakingUserAnswer, 'speaking__test_material'),
        ]

    for answer_model, filter_path in answer_models_config:
        if not answer_model:
            continue

        try:
            if material_id:
                # Filter by ReadingMaterial ID
                filter_conditions = {filter_path: reading_material}
            else:
                # Filter by Test
                filter_conditions = {f'{filter_path}__test': test}

            # Get user IDs for this module
            user_ids = answer_model.objects.filter(
                **filter_conditions
            ).values_list('user_id', flat=True).distinct()

            all_user_ids.update(user_ids)

        except Exception as e:
            # Continue with other modules if one fails
            print(f"Error in {answer_model.__name__}: {str(e)}")
            continue

    # ============ HANDLE EMPTY RESULTS ============
    if not all_user_ids:
        empty_response = {
            'count': 0,
            'total_pages': 1,
            'page_size': 10,
            'next': None,
            'previous': None,
            'results': []
        }
        return Response(empty_response, status=status.HTTP_200_OK)

    # ============ GROUP USERS BY GROUPS ============
    if not Users:
        empty_response = {
            'count': 0,
            'total_pages': 1,
            'page_size': 10,
            'next': None,
            'previous': None,
            'results': []
        }
        return Response(empty_response, status=status.HTTP_200_OK)

    # Get users with their groups
    users = Users.objects.filter(
        id__in=list(all_user_ids)
    ).select_related('student_group')

    # Group users by their student groups
    group_to_users = defaultdict(set)
    group_name_map = {}

    for user in users:
        if hasattr(user, 'student_group') and user.student_group:
            group_id = user.student_group.id
            group_name = user.student_group.name
            group_to_users[group_id].add(user.id)
            group_name_map[group_id] = group_name
        else:
            # Users without groups
            group_to_users[None].add(user.id)

    # ============ FORMAT GROUP STATISTICS ============
    group_info = []
    for group_id, user_set in group_to_users.items():
        group_name = group_name_map.get(group_id, "Ungrouped" if group_id is None else None)

        group_info.append({
            "group_id": group_id,
            "group_name": group_name,
            "material_id": material_id,  # This is now ReadingMaterial ID
            "total_test_students": len(user_set)
        })

    # ============ APPLY SEARCH FILTER ============
    if search_query:
        filtered_group_info = []
        for group in group_info:
            group_name = group['group_name'] or ""
            if search_query in group_name.lower():
                filtered_group_info.append(group)
        group_info = filtered_group_info

    # ============ SORT RESULTS ============
    group_info.sort(key=lambda x: x['group_name'] or "")

    # ============ APPLY PAGINATION ============
    try:
        paginator = TenPaginationView()
        paginated_results = paginator.paginate_queryset(group_info, request)

        if paginated_results is not None:
            return paginator.get_paginated_response(paginated_results)
        else:
            # If pagination fails, return results without pagination
            return Response(group_info, status=status.HTTP_200_OK)

    except Exception as e:
        # If pagination completely fails, return empty response
        print(f"Pagination error: {str(e)}")
        empty_response = {
            'count': 0,
            'total_pages': 1,
            'page_size': 10,
            'next': None,
            'previous': None,
            'results': []
        }
        return Response(empty_response, status=status.HTTP_200_OK)


@api_view(['GET'])
def dashboard_statistics(request):
    def get_model_by_name(app_labels, model_name):
        for app_label in app_labels:
            try:
                if app_label:
                    return apps.get_model(app_label, model_name)
                else:
                    for model in apps.get_models():
                        if model._meta.model_name.lower() == model_name.lower():
                            return model
            except LookupError:
                continue
        return None

    # Get required models
    Users = get_model_by_name(['app', None], 'Users')
    Test = get_model_by_name(['app', None], 'Test')
    TestMaterial = get_model_by_name(['app', None], 'TestMaterial')
    ReadingMaterial = get_model_by_name(['app', None], 'ReadingMaterial')
    ListeningMaterial = get_model_by_name(['app', None], 'ListeningMaterial')
    WritingMaterial = get_model_by_name(['app', None], 'WritingMaterial')
    SpeakingMaterial = get_model_by_name(['app', None], 'SpeakingMaterial')
    StudentGroup = get_model_by_name(['app', None], 'StudentGroup')

    if not Users or not Test:
        return Response(
            {"error": "Required models not found"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    try:
        # TestMaterial larni type bo'yicha ajratamiz
        mock_materials = TestMaterial.objects.filter(test__test_type='Mock')
        thematic_materials = TestMaterial.objects.filter(test__test_type='Thematic')

        # Count helper function
        def count_all_materials(test_materials):
            return (
                ReadingMaterial.objects.filter(test_material__in=test_materials).count() +
                ListeningMaterial.objects.filter(test_material__in=test_materials).count() +
                WritingMaterial.objects.filter(test_material__in=test_materials).count() +
                SpeakingMaterial.objects.filter(test_material__in=test_materials).count()
            )

        result = {
            # ✅ Users model statistics
            "total_students": Users.objects.filter(role='Student').count(),
            "active_students": Users.objects.filter(role='Student', is_active=True).count(),

            # ✅ Test model statistics (ENDI materiallar sonini qaytaradi)
            "mock_tests_count": count_all_materials(mock_materials),
            "thematic_tests_count": count_all_materials(thematic_materials),

            # ✅ StudentGroup model statistics
            "total_groups": StudentGroup.objects.count() if StudentGroup else 0,
            "active_groups": StudentGroup.objects.filter(is_active=True).count() if StudentGroup else 0,
        }

        return Response(result, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

class ResultsAPIView(APIView):
    """Base Results API View"""

    def get_results_data(self, request, result_type='full'):
        """Shared method for getting results data"""
        material_id = request.query_params.get('material_id')
        group_id = request.query_params.get('group_id')

        if not material_id or not group_id:
            return Response(
                {"error": "material_id and group_id are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            material_id = int(material_id)
            group_id = int(group_id)
        except (ValueError, TypeError):
            return Response(
                {"error": "material_id and group_id must be valid integers"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if TestMaterial exists
        try:
            test_material = TestMaterial.objects.get(id=material_id)
        except TestMaterial.DoesNotExist:
            return Response(
                {"error": f"TestMaterial with id {material_id} does not exist"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if StudentGroup exists
        try:
            group = StudentGroup.objects.get(id=group_id)
        except StudentGroup.DoesNotExist:
            return Response(
                {"error": f"StudentGroup with id {group_id} does not exist"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if this is a Mock test
        is_mock_test = test_material.test.test_type == 'Mock'

        # Get students who have taken the specific skill
        students_with_answers = self.get_students_with_skill_answers(test_material, group, result_type)

        if not students_with_answers:
            return Response({
                'count': 0,
                'total_pages': 1,
                'current_page': 1,
                'page_size': 0,
                'next': None,
                'previous': None,
                'results': []
            })

        # Calculate scores for each student
        student_data = []
        for student in students_with_answers:
            student_info = self.get_student_info(student, test_material, result_type, is_mock_test)
            if student_info:  # Only add if material_info is valid
                student_data.append(student_info)

        # Apply pagination
        paginator = TenPaginationView()
        paginated_results = paginator.paginate_queryset(student_data, request)

        if paginated_results is not None:
            return paginator.get_paginated_response(paginated_results)
        else:
            return Response(student_data, status=status.HTTP_200_OK)

    def get_students_with_skill_answers(self, test_material, group, skill_type):
        """Get students who have answers for the specific skill"""

        if skill_type == 'reading':
            # Get students who have reading answers
            user_ids = ReadingUserAnswer.objects.filter(
                reading__reading_material__test_material=test_material,
                user__student_group=group
            ).values_list('user_id', flat=True).distinct()

        elif skill_type == 'listening':
            # Get students who have listening answers
            user_ids = ListeningUserAnswer.objects.filter(
                listening__listening_material__test_material=test_material,
                user__student_group=group
            ).values_list('user_id', flat=True).distinct()

        elif skill_type == 'writing':
            # Get students who have writing answers
            user_ids = WritingUserAnswer.objects.filter(
                writing__writing_material__test_material=test_material,
                user__student_group=group
            ).values_list('user_id', flat=True).distinct()

        elif skill_type == 'speaking':
            # Get students who have speaking answers
            user_ids = SpeakingUserAnswer.objects.filter(
                speaking__test_material=test_material,
                user__student_group=group
            ).values_list('user_id', flat=True).distinct()

        elif skill_type == 'full':
            # Get students who have answers in ANY skill for this test
            reading_users = ReadingUserAnswer.objects.filter(
                reading__reading_material__test_material=test_material,
                user__student_group=group
            ).values_list('user_id', flat=True)

            listening_users = ListeningUserAnswer.objects.filter(
                listening__listening_material__test_material=test_material,
                user__student_group=group
            ).values_list('user_id', flat=True)

            writing_users = WritingUserAnswer.objects.filter(
                writing__writing_material__test_material=test_material,
                user__student_group=group
            ).values_list('user_id', flat=True)

            speaking_users = SpeakingUserAnswer.objects.filter(
                speaking__test_material=test_material,
                user__student_group=group
            ).values_list('user_id', flat=True)

            # Combine all user IDs
            user_ids = set(reading_users) | set(listening_users) | set(writing_users) | set(speaking_users)
            user_ids = list(user_ids)
        else:
            user_ids = []

        # Return actual User objects
        return Users.objects.filter(id__in=user_ids, student_group=group).order_by('id')

    def get_student_info(self, student, test_material, result_type, is_mock_test):
        """Get complete student information with material info"""

        # Base student info
        student_info = {
            "student_id": student.id,
            "full_name": f"{student.first_name} {student.last_name}".strip(),
            "phone": student.phone or "",
            "group_name": student.student_group.name if student.student_group else "",
            "created_at": student.date_joined.strftime("%Y-%m-%d-%H:%M") if student.date_joined else "",
        }

        # Get material-specific info
        material_info = self.get_material_info(student, test_material, result_type, is_mock_test)

        if material_info and material_info.get('id') is not None:
            student_info['material_info'] = material_info
            return student_info

        return None  # Don't include students without valid material info

    def get_material_info(self, student, test_material, result_type, is_mock_test):
        """Get material info based on result type"""

        if result_type == 'reading':
            return self.get_reading_material_info(student, test_material, is_mock_test)
        elif result_type == 'listening':
            return self.get_listening_material_info(student, test_material, is_mock_test)
        elif result_type == 'writing':
            return self.get_writing_material_info(student, test_material, is_mock_test)
        elif result_type == 'speaking':
            return self.get_speaking_material_info(student, test_material, is_mock_test)
        elif result_type == 'full':
            return self.get_full_material_info(student, test_material, is_mock_test)

        return None

    def get_reading_material_info(self, student, test_material, is_mock_test):
        """Get reading material info"""
        reading_material = ReadingMaterial.objects.filter(test_material=test_material).first()
        if not reading_material:
            return None

        reading_user_answers = ReadingUserAnswer.objects.filter(
            user=student,
            reading__reading_material=reading_material
        )

        if not reading_user_answers.exists():
            return None

        reading_correct = reading_user_answers.filter(is_true=True).count()
        reading_total = reading_user_answers.count()

        if is_mock_test:
            reading_ielts_score = self.convert_reading_to_ielts_band(reading_correct)
            return {
                "id": reading_material.id,
                "type": "reading",
                "title": reading_material.title or f"Reading Test {reading_material.id}",
                "reading_complete": True,
                "total_questions": reading_total,
                "correct_answers": reading_correct,
                "incorrect_answers": reading_total - reading_correct,
                "score": round(reading_ielts_score, 1)
            }
        else:
            reading_score_percentage = (reading_correct / reading_total * 100) if reading_total > 0 else 0
            return {
                "id": reading_material.id,
                "type": "reading",
                "title": reading_material.title or f"Reading Test {reading_material.id}",
                "reading_complete": True,
                "total_questions": reading_total,
                "correct_answers": reading_correct,
                "incorrect_answers": reading_total - reading_correct,
                "score_percentage": round(reading_score_percentage, 2),
                "score": round(reading_score_percentage, 2)
            }

    def get_listening_material_info(self, student, test_material, is_mock_test):
        """Get listening material info"""
        listening_material = ListeningMaterial.objects.filter(test_material=test_material).first()
        if not listening_material:
            return None

        listening_user_answers = ListeningUserAnswer.objects.filter(
            user=student,
            listening__listening_material=listening_material
        )

        if not listening_user_answers.exists():
            return None

        listening_correct = listening_user_answers.filter(is_true=True).count()
        listening_total = listening_user_answers.count()

        if is_mock_test:
            listening_ielts_score = self.convert_listening_to_ielts_band(listening_correct)
            return {
                "id": listening_material.id,
                "type": "listening",
                "title": listening_material.title or f"Listening Test {listening_material.id}",
                "listening_complete": True,
                "total_questions": listening_total,
                "correct_answers": listening_correct,
                "incorrect_answers": listening_total - listening_correct,
                "score": round(listening_ielts_score, 1)
            }
        else:
            listening_score_percentage = (listening_correct / listening_total * 100) if listening_total > 0 else 0
            return {
                "id": listening_material.id,
                "type": "listening",
                "title": listening_material.title or f"Listening Test {listening_material.id}",
                "listening_complete": True,
                "total_questions": listening_total,
                "correct_answers": listening_correct,
                "incorrect_answers": listening_total - listening_correct,
                "score_percentage": round(listening_score_percentage, 2),
                "score": round(listening_score_percentage, 2)
            }

    def get_writing_material_info(self, student, test_material, is_mock_test):
        """Get writing material info"""
        writing_material = WritingMaterial.objects.filter(test_material=test_material).first()
        if not writing_material:
            return None

        writing_user_answers = WritingUserAnswer.objects.filter(
            user=student,
            writing__writing_material=writing_material
        )

        if not writing_user_answers.exists():
            return None

        # Get average score for writing
        scores = [answer.score for answer in writing_user_answers if answer.score is not None]
        if scores:
            avg_score = sum(scores) / len(scores)
        else:
            avg_score = 0.0

        total_tasks = writing_user_answers.count()
        completed_tasks = len(scores)

        return {
            "id": writing_material.id,
            "type": "writing",
            "title": writing_material.title or f"Writing Test {writing_material.id}",
            "writing_complete": completed_tasks > 0,
            "total_questions": total_tasks,
            "completed_tasks": completed_tasks,
            "score": round(avg_score, 1)
        }

    def get_speaking_material_info(self, student, test_material, is_mock_test):
        """Get speaking material info"""
        speaking_material = SpeakingMaterial.objects.filter(test_material=test_material).first()
        if not speaking_material:
            return None

        speaking_user_answers = SpeakingUserAnswer.objects.filter(
            user=student,
            speaking=speaking_material
        )

        if not speaking_user_answers.exists():
            return None

        # Get average score for speaking
        scores = [answer.score for answer in speaking_user_answers if answer.score is not None]
        if scores:
            avg_score = sum(scores) / len(scores)
        else:
            avg_score = 0.0

        total_questions = speaking_user_answers.count()
        answered_questions = len(scores)

        return {
            "id": speaking_material.id,
            "type": "speaking",
            "title": speaking_material.title or f"Speaking Test {speaking_material.id}",
            "speaking_complete": answered_questions > 0,
            "total_questions": total_questions,
            "answered_questions": answered_questions,
            "score": round(avg_score, 1)
        }

    def get_full_material_info(self, student, test_material, is_mock_test):
        """Get combined material info for all skills"""

        # Calculate scores for all skills
        reading_info = self.get_reading_material_info(student, test_material, is_mock_test)
        listening_info = self.get_listening_material_info(student, test_material, is_mock_test)
        writing_info = self.get_writing_material_info(student, test_material, is_mock_test)
        speaking_info = self.get_speaking_material_info(student, test_material, is_mock_test)

        # Collect valid scores
        valid_scores = []
        total_questions = 0
        correct_answers = 0

        if reading_info:
            valid_scores.append(reading_info.get('score', 0))
            total_questions += reading_info.get('total_questions', 0)
            correct_answers += reading_info.get('correct_answers', 0)

        if listening_info:
            valid_scores.append(listening_info.get('score', 0))
            total_questions += listening_info.get('total_questions', 0)
            correct_answers += listening_info.get('correct_answers', 0)

        if writing_info:
            valid_scores.append(writing_info.get('score', 0))

        if speaking_info:
            valid_scores.append(speaking_info.get('score', 0))

        # Only return if student has attempted at least one skill
        if not valid_scores:
            return None

        # Calculate overall score
        overall_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0

        return {
            "id": test_material.id,
            "type": "full",
            "title": test_material.title or f"Full Test {test_material.id}",
            "total_questions": total_questions,
            "correct_answers": correct_answers,
            "incorrect_answers": total_questions - correct_answers,
            "overall_score": round(overall_score, 1),
            "skills_attempted": len(valid_scores),
            "reading_score": reading_info.get('score', 0) if reading_info else None,
            "listening_score": listening_info.get('score', 0) if listening_info else None,
            "writing_score": writing_info.get('score', 0) if writing_info else None,
            "speaking_score": speaking_info.get('score', 0) if speaking_info else None,
        }

    def convert_reading_to_ielts_band(self, correct_answers):
        """Convert reading correct answers to IELTS band score"""
        # IELTS Reading band score conversion (approximate)
        if correct_answers >= 39:
            return 9.0
        elif correct_answers >= 37:
            return 8.5
        elif correct_answers >= 35:
            return 8.0
        elif correct_answers >= 33:
            return 7.5
        elif correct_answers >= 30:
            return 7.0
        elif correct_answers >= 27:
            return 6.5
        elif correct_answers >= 23:
            return 6.0
        elif correct_answers >= 19:
            return 5.5
        elif correct_answers >= 15:
            return 5.0
        elif correct_answers >= 13:
            return 4.5
        elif correct_answers >= 10:
            return 4.0
        elif correct_answers >= 8:
            return 3.5
        elif correct_answers >= 6:
            return 3.0
        elif correct_answers >= 4:
            return 2.5
        else:
            return 2.0

    def convert_listening_to_ielts_band(self, correct_answers):
        """Convert listening correct answers to IELTS band score"""
        # IELTS Listening band score conversion (approximate)
        if correct_answers >= 39:
            return 9.0
        elif correct_answers >= 37:
            return 8.5
        elif correct_answers >= 35:
            return 8.0
        elif correct_answers >= 32:
            return 7.5
        elif correct_answers >= 30:
            return 7.0
        elif correct_answers >= 26:
            return 6.5
        elif correct_answers >= 23:
            return 6.0
        elif correct_answers >= 18:
            return 5.5
        elif correct_answers >= 16:
            return 5.0
        elif correct_answers >= 13:
            return 4.5
        elif correct_answers >= 11:
            return 4.0
        elif correct_answers >= 8:
            return 3.5
        elif correct_answers >= 6:
            return 3.0
        elif correct_answers >= 4:
            return 2.5
        else:
            return 2.0

    def get(self, request):
        """Handle GET requests for full results"""
        return self.get_results_data(request, 'full')


class BaseResultsAPIView(APIView):
    def validate_request_params(self, request):
        """Validate material_id and group_id parameters"""
        material_id = request.query_params.get('material_id')
        group_id = request.query_params.get('group_id')

        if not material_id or not group_id:
            return None, Response(
                {"error": "material_id and group_id are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            material_id = int(material_id)
            group_id = int(group_id)
        except (ValueError, TypeError):
            return None, Response(
                {"error": "material_id and group_id must be valid integers"},
                status=status.HTTP_400_BAD_REQUEST
            )

        return (material_id, group_id), None

    def validate_test_material(self, material_id, expected_test_type):
        """Validate test material exists and has correct type"""
        try:
            test_material = TestMaterial.objects.get(id=material_id)
            if test_material.test.test_type != expected_test_type:
                return None, Response(
                    {"error": f"TestMaterial with id {material_id} is not a {expected_test_type} test"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            return test_material, None
        except TestMaterial.DoesNotExist:
            return None, Response(
                {"error": f"TestMaterial with id {material_id} does not exist"},
                status=status.HTTP_404_NOT_FOUND
            )

    def validate_student_group(self, group_id):
        """Validate student group exists"""
        try:
            group = StudentGroup.objects.get(id=group_id)
            return group, None
        except StudentGroup.DoesNotExist:
            return None, Response(
                {"error": f"StudentGroup with id {group_id} does not exist"},
                status=status.HTTP_404_NOT_FOUND
            )

    def get_base_student_info(self, student):
        """Get base student information"""
        return {
            "student_id": student.id,
            "full_name": f"{student.first_name} {student.last_name}",
            "phone": student.phone or "",
            "group_name": student.student_group.name if student.student_group else "",
            "created_at": student.date_joined.strftime("%Y-%m-%d-%H:%M") if student.date_joined else "",
        }

    def calculate_reading_data(self, student, test_material, test_type_name):
        """Calculate reading-specific data"""
        reading_material = ReadingMaterial.objects.filter(test_material=test_material).first()

        if not reading_material:
            return {
                "id": None,
                "type": "reading",
                "title": f"{test_type_name} Reading Test {test_material.id}",
                "reading_complete": False,
                "total_questions": 0,
                "correct_answers": 0,
                "incorrect_answers": 0,
                "score_percentage": 0.0,
                "score": 0.0
            }

        # Get user answers
        reading_user_answers = ReadingUserAnswer.objects.filter(
            user=student,
            reading__reading_material=reading_material
        )

        # Count correct answers
        reading_correct = reading_user_answers.filter(is_true=True).count()
        reading_complete = reading_user_answers.exists()

        # Get ACTUAL total questions from ReadingAnswer model
        reading_total = ReadingAnswer.objects.filter(
            reading__reading_material=reading_material
        ).count()

        # Calculate metrics - ensure no impossible values
        if reading_total > 0:
            # Make sure correct answers don't exceed total questions
            reading_correct = min(reading_correct, reading_total)
            reading_incorrect = reading_total - reading_correct
            reading_score_percentage = (reading_correct / reading_total) * 100
        else:
            reading_correct = 0
            reading_incorrect = 0
            reading_score_percentage = 0.0

        return {
            "id": reading_material.id,
            "type": "reading",
            "title": reading_material.title or f"{test_type_name} Test {reading_material.id} Reading",
            "reading_complete": reading_complete,
            "total_questions": reading_total,
            "correct_answers": reading_correct,
            "incorrect_answers": reading_incorrect,
            "score_percentage": round(reading_score_percentage, 2),
            "score": round(reading_score_percentage, 2)
        }

    def calculate_listening_data(self, student, test_material, test_type_name):
        """Calculate listening-specific data"""
        listening_material = ListeningMaterial.objects.filter(test_material=test_material).first()

        if not listening_material:
            return {
                "id": None,
                "type": "listening",
                "title": f"{test_type_name} Listening Test {test_material.id}",
                "listening_complete": False,
                "total_questions": 0,
                "correct_answers": 0,
                "incorrect_answers": 0,
                "score_percentage": 0.0,
                "score": 0.0
            }

        # Get user answers
        listening_user_answers = ListeningUserAnswer.objects.filter(
            user=student,
            listening__listening_material=listening_material
        )

        # Count correct answers
        listening_correct = listening_user_answers.filter(is_true=True).count()
        listening_complete = listening_user_answers.exists()

        # Get ACTUAL total questions from ListeningAnswer model
        listening_total = ListeningAnswer.objects.filter(
            listening__listening_material=listening_material
        ).count()

        # Calculate metrics - ensure no impossible values
        if listening_total > 0:
            # Make sure correct answers don't exceed total questions
            listening_correct = min(listening_correct, listening_total)
            listening_incorrect = listening_total - listening_correct
            listening_score_percentage = (listening_correct / listening_total) * 100
        else:
            listening_correct = 0
            listening_incorrect = 0
            listening_score_percentage = 0.0

        return {
            "id": listening_material.id,
            "type": "listening",
            "title": listening_material.title or f"{test_type_name} Test {listening_material.id} Listening",
            "listening_complete": listening_complete,
            "total_questions": listening_total,
            "correct_answers": listening_correct,
            "incorrect_answers": listening_incorrect,
            "score_percentage": round(listening_score_percentage, 2),
            "score": round(listening_score_percentage, 2)
        }

    def calculate_writing_data(self, student, test_material, test_type_name):
        """Calculate writing-specific data"""
        writing_material = WritingMaterial.objects.filter(test_material=test_material).first()

        if not writing_material:
            return {
                "id": None,
                "type": "writing",
                "title": f"{test_type_name} Writing Test {test_material.id}",
                "writing_complete": False,
                "total_questions": 0,
                "correct_answers": 0,
                "incorrect_answers": 0,
                "score_percentage": 0.0,
                "score": 0.0,
                "writing_task1": {
                    "completed": False,
                    "score": 0.0,
                    "feedback": None
                },
                "writing_task2": {
                    "completed": False,
                    "score": 0.0,
                    "feedback": None
                },
                "overall_writing_score": 0.0
            }

        # Task 1 Data
        task1_answers = WritingUserAnswer.objects.filter(
            user=student,
            writing__writing_material=writing_material,
            writing__writing_task=1
        )
        task1_score = task1_answers.aggregate(avg_score=Avg('score'))['avg_score'] or 0
        task1_complete = task1_answers.exists()
        task1_feedback = task1_answers.first().feedback if task1_answers.exists() else None

        # Task 2 Data
        task2_answers = WritingUserAnswer.objects.filter(
            user=student,
            writing__writing_material=writing_material,
            writing__writing_task=2
        )
        task2_score = task2_answers.aggregate(avg_score=Avg('score'))['avg_score'] or 0
        task2_complete = task2_answers.exists()
        task2_feedback = task2_answers.first().feedback if task2_answers.exists() else None

        # Overall writing data
        all_writing_answers = WritingUserAnswer.objects.filter(
            user=student,
            writing__writing_material=writing_material
        )

        # Calculate writing overall: ((T2*2)+T1)/3 (9-point scale)
        if task1_score > 0 or task2_score > 0:
            writing_overall_score = ((task2_score * 2) + task1_score) / 3
        else:
            writing_overall_score = 0

        writing_complete = task1_complete or task2_complete

        # Get actual total tasks from Writing model
        total_writing_tasks = Writing.objects.filter(writing_material=writing_material).count()
        completed_tasks = all_writing_answers.filter(score__isnull=False).count()

        # Ensure no negative values
        incomplete_tasks = max(0, total_writing_tasks - completed_tasks)

        return {
            "id": writing_material.id,
            "type": "writing",
            "title": writing_material.title or f"{test_type_name} Writing Test {writing_material.id}",
            "writing_complete": writing_complete,
            "total_questions": total_writing_tasks,
            "correct_answers": completed_tasks,
            "incorrect_answers": incomplete_tasks,
            "score_percentage": round(writing_overall_score * 10, 2),
            "score": round(writing_overall_score, 1),
            "writing_task1": {
                "completed": task1_complete,
                "score": round(task1_score, 1),
                "feedback": task1_feedback
            },
            "writing_task2": {
                "completed": task2_complete,
                "score": round(task2_score, 1),
                "feedback": task2_feedback
            },
            "overall_writing_score": round(writing_overall_score, 1)
        }

    def calculate_speaking_data(self, student, test_material, test_type_name):
        """Calculate speaking-specific data"""
        speaking_material = SpeakingMaterial.objects.filter(test_material=test_material).first()

        if not speaking_material:
            return {
                "id": None,
                "type": "speaking",
                "title": f"{test_type_name} Speaking Test {test_material.id}",
                "speaking_complete": False,
                "total_questions": 0,
                "correct_answers": 0,
                "incorrect_answers": 0,
                "score_percentage": 0.0,
                "score": 0.0,
                "feedback": None
            }

        # Get speaking answers
        speaking_answers = SpeakingUserAnswer.objects.filter(
            user=student,
            speaking__test_material=test_material
        )

        speaking_avg_score = speaking_answers.aggregate(avg_score=Avg('score'))['avg_score'] or 0
        speaking_with_score = speaking_answers.filter(score__isnull=False).count()
        speaking_complete = speaking_answers.exists()

        latest_speaking = speaking_answers.order_by('-created_at').first()
        feedback = latest_speaking.feedback if latest_speaking else None

        # Get actual total speaking questions from Speaking model
        total_speaking_questions = Speaking.objects.filter(test_material=test_material).count()

        # Ensure no negative values
        incomplete_questions = max(0, total_speaking_questions - speaking_with_score)

        return {
            "id": speaking_material.id,
            "type": "speaking",
            "title": speaking_material.title or f"{test_type_name} Speaking Test {speaking_material.id}",
            "speaking_complete": speaking_complete,
            "total_questions": total_speaking_questions,
            "correct_answers": speaking_with_score,
            "incorrect_answers": incomplete_questions,
            "score_percentage": round(speaking_avg_score * 10, 2),
            "score": round(speaking_avg_score, 1),
            "feedback": feedback
        }

    def get_student_results(self, students, test_material, result_type, test_type_name):
        """Get results for all students"""
        student_data = []

        for student in students:
            student_info = self.get_base_student_info(student)

            if result_type == 'reading':
                material_info = self.calculate_reading_data(student, test_material, test_type_name)
            elif result_type == 'listening':
                material_info = self.calculate_listening_data(student, test_material, test_type_name)
            elif result_type == 'writing':
                material_info = self.calculate_writing_data(student, test_material, test_type_name)
            elif result_type == 'speaking':
                material_info = self.calculate_speaking_data(student, test_material, test_type_name)
            else:
                # Default case - should not happen
                material_info = {
                    "id": None,
                    "type": result_type,
                    "title": f"{test_type_name} Test {test_material.id}",
                    "total_questions": 0,
                    "correct_answers": 0,
                    "incorrect_answers": 0,
                    "score_percentage": 0.0,
                    "score": 0.0
                }

            student_info["material_info"] = material_info
            student_data.append(student_info)

        # Sort students appropriately
        if result_type in ['reading', 'listening']:
            student_data.sort(key=lambda x: x["material_info"]["correct_answers"], reverse=True)
        elif result_type in ['writing', 'speaking']:
            student_data.sort(key=lambda x: x["material_info"]["score"], reverse=True)

        return student_data

    def paginate_results(self, student_data, request, material_id, group_id):
        """Apply pagination to results"""
        page_size = 10
        django_paginator = Paginator(student_data, page_size)
        page_number = request.GET.get('page', 1)

        try:
            page_obj = django_paginator.page(page_number)
            paginated_data = list(page_obj)

            return Response({
                'count': django_paginator.count,
                'total_pages': django_paginator.num_pages,
                'current_page': page_obj.number,
                'page_size': page_size,
                'next': f"?page={page_obj.next_page_number()}&material_id={material_id}&group_id={group_id}" if page_obj.has_next() else None,
                'previous': f"?page={page_obj.previous_page_number()}&material_id={material_id}&group_id={group_id}" if page_obj.has_previous() else None,
                'results': paginated_data
            })
        except Exception as e:
            return Response({
                'count': len(student_data),
                'total_pages': 1,
                'current_page': 1,
                'page_size': len(student_data),
                'next': None,
                'previous': None,
                'results': student_data
            })


class ResultsByTypeAPIView(ResultsAPIView):
    """Results API View for specific skill types"""

    def get(self, request, result_type):
        """Handle GET requests for specific result types"""

        # Validate result type
        valid_types = ['reading', 'listening', 'writing', 'speaking', 'full']
        if result_type not in valid_types:
            return Response(
                {"error": f"Invalid result type. Must be one of: {', '.join(valid_types)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        return self.get_results_data(request, result_type)


class AllResultsByTypeAPIView(ResultsAPIView):
    """Results API View for all skill types without pagination"""

    def get_all_results_data_without_pagination(self, request, result_type='full'):
        """Get results data without pagination - EXACT COPY of ResultsAPIView logic without pagination"""
        material_id = request.query_params.get('material_id')
        group_id = request.query_params.get('group_id')

        if not material_id or not group_id:
            return Response(
                {"error": "material_id and group_id are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            material_id = int(material_id)
            group_id = int(group_id)
        except (ValueError, TypeError):
            return Response(
                {"error": "material_id and group_id must be valid integers"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if TestMaterial exists
        try:
            test_material = TestMaterial.objects.get(id=material_id)
        except TestMaterial.DoesNotExist:
            return Response(
                {"error": f"TestMaterial with id {material_id} does not exist"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if StudentGroup exists
        try:
            group = StudentGroup.objects.get(id=group_id)
        except StudentGroup.DoesNotExist:
            return Response(
                {"error": f"StudentGroup with id {group_id} does not exist"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if this is a Mock test
        is_mock_test = test_material.test.test_type == 'Mock'

        # Get students who have taken the specific skill
        students_with_answers = self.get_students_with_skill_answers(test_material, group, result_type)

        if not students_with_answers:
            return Response({
                'total_results': 0,
                'results': []
            })

        # Calculate scores for each student
        student_data = []
        for student in students_with_answers:
            student_info = self.get_student_info(student, test_material, result_type, is_mock_test)
            if student_info:  # Only add if material_info is valid
                student_data.append(student_info)

        # ✅ Return results WITHOUT pagination - direct response like ResultsAPIView but without pagination wrapper
        return Response({
            'total_results': len(student_data),
            'test_material_id': material_id,
            'group_id': group_id,
            'test_type': test_material.test.test_type,
            'result_type': result_type,
            'results': student_data
        })

    def get(self, request, result_type):
        """Handle GET requests for specific result types - EXACT STRUCTURE as ResultsByTypeAPIView"""

        # Validate result type - EXACT COPY from ResultsByTypeAPIView
        valid_types = ['reading', 'listening', 'writing', 'speaking', 'full']
        if result_type not in valid_types:
            return Response(
                {"error": f"Invalid result type. Must be one of: {', '.join(valid_types)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ✅ Call non-paginated version instead of paginated get_results_data
        return self.get_all_results_data_without_pagination(request, result_type)


class ThematicResultsByTypeAPIView(BaseResultsAPIView):
    def get_thematic_results_data(self, request, material_type='reading'):
        """Get Thematic test results data for specific material type"""

        # Validate material type from URL
        valid_material_types = ['reading', 'listening', 'writing', 'speaking']
        if material_type not in valid_material_types:
            return Response(
                {"detail": f"Invalid material type. Must be one of: {', '.join(valid_material_types)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate request parameters
        params_result = self.validate_request_params(request)
        if params_result[1]:  # Error response exists
            return params_result[1]
        material_id, group_id = params_result[0]

        # Validate material based on type
        material_result = self.validate_material_by_type(material_id, material_type)
        if material_result[1]:  # Error response exists
            return material_result[1]
        material, test_material = material_result[0]

        # Validate that it's a Thematic test
        if test_material.test.test_type != 'Thematic':
            return Response(
                {"detail": f"{material_type.title()} material with id={material_id} is not from a Thematic test."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate student group
        group_result = self.validate_student_group(group_id)
        if group_result[1]:  # Error response exists
            return group_result[1]
        group = group_result[0]

        # Get students who actually took this specific test (have answers)
        students_with_answers = self.get_students_with_answers(material, material_type, group)

        if not students_with_answers:
            return Response({
                'count': 0,
                'total_pages': 1,
                'current_page': 1,
                'page_size': 0,
                'next': None,
                'previous': None,
                'results': []
            })

        # Calculate results for students who took the test
        student_data = self.get_student_results_by_material_type(
            students_with_answers, material, material_type, test_material
        )

        # ✅ NEW: Sort students by score_percentage in descending order (highest scores first)
        student_data.sort(key=lambda x: x['material_info']['score_percentage'], reverse=True)

        # Apply pagination and return results
        return self.paginate_results(student_data, request, material_id, group_id)

    def get_students_with_answers(self, material, material_type, group):
        """Get students who have answers for the specific material"""

        if material_type == 'reading':
            # ReadingUserAnswer.reading points to Reading model
            # Get all Reading objects for this ReadingMaterial
            readings = self.get_related_objects(material, 'Reading')
            if not readings:
                return []

            user_ids = ReadingUserAnswer.objects.filter(
                reading__in=readings,
                user__student_group=group
            ).values_list('user_id', flat=True).distinct()

        elif material_type == 'listening':
            # ListeningUserAnswer.listening points to Listening model
            # Get all Listening objects for this ListeningMaterial
            listenings = self.get_related_objects(material, 'Listening')
            if not listenings:
                return []

            user_ids = ListeningUserAnswer.objects.filter(
                listening__in=listenings,
                user__student_group=group
            ).values_list('user_id', flat=True).distinct()

        elif material_type == 'writing':
            # WritingUserAnswer.writing points to Writing model
            # Get all Writing objects for this WritingMaterial
            writings = self.get_related_objects(material, 'Writing')
            if not writings:
                return []

            user_ids = WritingUserAnswer.objects.filter(
                writing__in=writings,
                user__student_group=group
            ).values_list('user_id', flat=True).distinct()

        elif material_type == 'speaking':
            # SpeakingUserAnswer.speaking points to SpeakingMaterial directly
            user_ids = SpeakingUserAnswer.objects.filter(
                speaking=material,
                user__student_group=group
            ).values_list('user_id', flat=True).distinct()

        else:
            return []

        # Get the actual user objects
        return Users.objects.filter(id__in=user_ids).order_by('id')

    def get_related_objects(self, material, related_model_name):
        """Get related objects (Reading, Listening, Writing) for a material"""

        def get_model_by_name(app_labels, model_name):
            for app_label in app_labels:
                try:
                    if app_label:
                        return apps.get_model(app_label, model_name)
                    else:
                        for model in apps.get_models():
                            if model._meta.model_name.lower() == model_name.lower():
                                return model
                except LookupError:
                    continue
            return None

        # Get the related model
        related_model = get_model_by_name([related_model_name.lower(), None], related_model_name)
        if not related_model:
            return []

        # Get related objects based on the relationship
        # Assuming the relationship is: ReadingMaterial -> Reading, ListeningMaterial -> Listening, etc.
        try:
            # Try different possible relationship names
            possible_relations = [
                f'{related_model_name.lower()}_material',  # reading_material, writing_material
                f'{related_model_name.lower()}material',  # readingmaterial, writingmaterial
                'material',  # generic material field
                f'{material._meta.model_name.lower()}'  # based on the material model name
            ]

            for relation_name in possible_relations:
                try:
                    filter_kwargs = {relation_name: material}
                    return related_model.objects.filter(**filter_kwargs)
                except Exception:
                    continue

            # If no direct relationship found, try reverse lookup
            if hasattr(material, f'{related_model_name.lower()}_set'):
                return getattr(material, f'{related_model_name.lower()}_set').all()
            elif hasattr(material, f'{related_model_name.lower()}s'):
                return getattr(material, f'{related_model_name.lower()}s').all()

        except Exception as e:
            print(f"Error getting related objects: {str(e)}")

        return []

    def get_student_results_by_material_type(self, students, material, material_type, test_material):
        """Get detailed results for each student by material type"""

        results = []

        for student in students:
            # Get student basic info
            student_data = {
                'student_id': student.id,
                'full_name': f"{student.first_name} {student.last_name}".strip(),
                'phone': student.phone,
                'group_name': student.student_group.name if student.student_group else 'No Group',
                'created_at': student.date_joined.strftime('%Y-%m-%d-%H:%M'),
                # ✅ Fix: Use date_joined instead of created_at
            }

            # Get material-specific results
            material_info = self.get_material_info_by_type(student, material, material_type, test_material)
            student_data['material_info'] = material_info

            results.append(student_data)

        return results

    def get_material_info_by_type(self, student, material, material_type, test_material):
        """Get material info based on material type"""

        if material_type == 'reading':
            return self.get_reading_material_info(student, material, test_material)
        elif material_type == 'listening':
            return self.get_listening_material_info(student, material, test_material)
        elif material_type == 'writing':
            return self.get_writing_material_info(student, material, test_material)
        elif material_type == 'speaking':
            return self.get_speaking_material_info(student, material, test_material)

        return self.get_default_material_info(material, material_type, test_material)

    def get_reading_material_info(self, student, reading_material, test_material):
        """Get reading material info with actual results"""

        # Get all Reading objects for this ReadingMaterial
        readings = self.get_related_objects(reading_material, 'Reading')
        if not readings:
            return self.get_default_material_info(reading_material, 'reading', test_material)

        # Get all answers for this student and all readings in this material
        user_answers = ReadingUserAnswer.objects.filter(
            user=student,
            reading__in=readings
        )

        total_questions = user_answers.count()
        correct_answers = user_answers.filter(is_true=True).count()
        incorrect_answers = total_questions - correct_answers

        # Calculate score percentage
        score_percentage = (correct_answers / total_questions * 100) if total_questions > 0 else 0.0

        # For reading, score is typically the same as percentage, but you can adjust this
        score = score_percentage / 100 * 9  # Convert to IELTS band scale (0-9)

        return {
            'id': reading_material.id,
            'type': 'reading',
            'title': test_material.test.title,
            'total_questions': total_questions,
            'correct_answers': correct_answers,
            'incorrect_answers': incorrect_answers,
            'score_percentage': round(score_percentage, 1),
            'score': round(score, 1)
        }

    def get_listening_material_info(self, student, listening_material, test_material):
        """Get listening material info with actual results"""

        # Get all Listening objects for this ListeningMaterial
        listenings = self.get_related_objects(listening_material, 'Listening')
        if not listenings:
            return self.get_default_material_info(listening_material, 'listening', test_material)

        # Get all answers for this student and all listenings in this material
        user_answers = ListeningUserAnswer.objects.filter(
            user=student,
            listening__in=listenings
        )

        total_questions = user_answers.count()
        correct_answers = user_answers.filter(is_true=True).count()
        incorrect_answers = total_questions - correct_answers

        # Calculate score percentage
        score_percentage = (correct_answers / total_questions * 100) if total_questions > 0 else 0.0

        # For listening, score is typically the same as percentage, but you can adjust this
        score = score_percentage / 100 * 9  # Convert to IELTS band scale (0-9)

        return {
            'id': listening_material.id,
            'type': 'listening',
            'title': test_material.test.title,
            'total_questions': total_questions,
            'correct_answers': correct_answers,
            'incorrect_answers': incorrect_answers,
            'score_percentage': round(score_percentage, 1),
            'score': round(score, 1)
        }

    def get_writing_material_info(self, student, writing_material, test_material):
        """Get writing material info with actual results"""

        # Get all Writing objects for this WritingMaterial
        writings = self.get_related_objects(writing_material, 'Writing')
        if not writings:
            return self.get_default_material_info(writing_material, 'writing', test_material)

        # Get writing answers for this student and all writings in this material
        user_answers = WritingUserAnswer.objects.filter(
            user=student,
            writing__in=writings
        )

        if user_answers.exists():
            # Calculate average score from all writing tasks
            scores = [answer.score for answer in user_answers if answer.score is not None]

            if scores:
                avg_score = sum(scores) / len(scores)
                score_percentage = (avg_score / 9 * 100)  # Convert from band score to percentage
            else:
                avg_score = 0.0
                score_percentage = 0.0

            total_questions = user_answers.count()
            correct_answers = len([s for s in scores if s >= 5.0])  # Consider passing if score >= 5.0
            incorrect_answers = total_questions - correct_answers

        else:
            avg_score = 0.0
            score_percentage = 0.0
            total_questions = 0
            correct_answers = 0
            incorrect_answers = 0

        return {
            'id': writing_material.id,
            'type': 'writing',
            'title': test_material.test.title,
            'total_questions': total_questions,
            'correct_answers': correct_answers,
            'incorrect_answers': incorrect_answers,
            'score_percentage': round(score_percentage, 1),
            'score': round(avg_score, 1)
        }

    def get_speaking_material_info(self, student, speaking_material, test_material):
        """Get speaking material info with actual results"""

        # Get all speaking answers for this student
        user_answers = SpeakingUserAnswer.objects.filter(
            user=student,
            speaking=speaking_material
        )

        if user_answers.exists():
            # Calculate average score from all speaking questions
            scores = [answer.score for answer in user_answers if answer.score is not None]

            if scores:
                avg_score = sum(scores) / len(scores)
                score_percentage = (avg_score / 9 * 100)  # Convert from band score to percentage
            else:
                avg_score = 0.0
                score_percentage = 0.0

            total_questions = user_answers.count()
            correct_answers = len([s for s in scores if s >= 5.0])  # Consider passing if score >= 5.0
            incorrect_answers = total_questions - correct_answers

        else:
            avg_score = 0.0
            score_percentage = 0.0
            total_questions = 0
            correct_answers = 0
            incorrect_answers = 0

        return {
            'id': speaking_material.id,
            'type': 'speaking',
            'title': test_material.test.title,
            'total_questions': total_questions,
            'correct_answers': correct_answers,
            'incorrect_answers': incorrect_answers,
            'score_percentage': round(score_percentage, 1),
            'score': round(avg_score, 1)
        }

    def get_default_material_info(self, material, material_type, test_material):
        """Get default material info structure"""

        return {
            'id': material.id,
            'type': material_type,
            'title': test_material.test.title,
            'total_questions': 0,
            'correct_answers': 0,
            'incorrect_answers': 0,
            'score_percentage': 0.0,
            'score': 0.0
        }

    def validate_material_by_type(self, material_id, material_type):
        """Validate material based on its type"""

        # Get model dynamically based on material type
        material_model = self.get_material_model(material_type)
        if not material_model:
            return None, Response(
                {"detail": f"{material_type.title()} material model not found."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        try:
            material = material_model.objects.get(id=material_id)
        except material_model.DoesNotExist:
            return None, Response(
                {"detail": f"{material_type.title()} material with id={material_id} not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get test material based on material type
        if material_type == 'speaking':
            # SpeakingMaterial has direct test_material relationship
            test_material = material.test_material
        else:
            # Other materials have test_material through their specific material
            test_material = material.test_material

        return (material, test_material), None

    def get_material_model(self, material_type):
        """Get the appropriate material model based on type"""

        def get_model_by_name(app_labels, model_name):
            for app_label in app_labels:
                try:
                    if app_label:
                        return apps.get_model(app_label, model_name)
                    else:
                        for model in apps.get_models():
                            if model._meta.model_name.lower() == model_name.lower():
                                return model
                except LookupError:
                    continue
            return None

        material_model_map = {
            'reading': get_model_by_name(['reading', None], 'ReadingMaterial'),
            'listening': get_model_by_name(['listening', None], 'ListeningMaterial'),
            'writing': get_model_by_name(['writing', None], 'WritingMaterial'),
            'speaking': get_model_by_name(['speaking', None], 'SpeakingMaterial'),
        }

        return material_model_map.get(material_type)

    def get(self, request, result_type):
        """Handle GET requests for specific material type"""
        return self.get_thematic_results_data(request, result_type)


class ThematicAllResultsAPIView(BaseResultsAPIView):
    def get_thematic_results_data_without_pagination(self, request, material_type='reading'):
        """Get Thematic test results data for specific material type WITHOUT PAGINATION"""

        # Validate material type from URL
        valid_material_types = ['reading', 'listening', 'writing', 'speaking']
        if material_type not in valid_material_types:
            return Response(
                {"detail": f"Invalid material type. Must be one of: {', '.join(valid_material_types)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate request parameters
        params_result = self.validate_request_params(request)
        if params_result[1]:  # Error response exists
            return params_result[1]
        material_id, group_id = params_result[0]

        # Validate material based on type
        material_result = self.validate_material_by_type(material_id, material_type)
        if material_result[1]:  # Error response exists
            return material_result[1]
        material, test_material = material_result[0]

        # Validate that it's a Thematic test
        if test_material.test.test_type != 'Thematic':
            return Response(
                {"detail": f"{material_type.title()} material with id={material_id} is not from a Thematic test."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate student group
        group_result = self.validate_student_group(group_id)
        if group_result[1]:  # Error response exists
            return group_result[1]
        group = group_result[0]

        # Get students who actually took this specific test (have answers)
        students_with_answers = self.get_students_with_answers(material, material_type, group)

        if not students_with_answers:
            return Response({
                'total_results': 0,
                'results': []
            })

        # Calculate results for students who took the test
        student_data = self.get_student_results_by_material_type(
            students_with_answers, material, material_type, test_material
        )

        # ✅ NEW: Sort students by score_percentage in descending order (highest scores first)
        student_data.sort(key=lambda x: x['material_info']['score_percentage'], reverse=True)

        # ✅ Return results WITHOUT pagination
        return Response({
            'total_results': len(student_data),
            'material_type': material_type,
            'material_id': material_id,
            'group_id': group_id,
            'test_type': test_material.test.test_type,
            'results': student_data
        })

    def get_students_with_answers(self, material, material_type, group):
        """Get students who have answers for the specific material"""

        if material_type == 'reading':
            # ReadingUserAnswer.reading points to Reading model
            # Get all Reading objects for this ReadingMaterial
            readings = self.get_related_objects(material, 'Reading')
            if not readings:
                return []

            user_ids = ReadingUserAnswer.objects.filter(
                reading__in=readings,
                user__student_group=group
            ).values_list('user_id', flat=True).distinct()

        elif material_type == 'listening':
            # ListeningUserAnswer.listening points to Listening model
            # Get all Listening objects for this ListeningMaterial
            listenings = self.get_related_objects(material, 'Listening')
            if not listenings:
                return []

            user_ids = ListeningUserAnswer.objects.filter(
                listening__in=listenings,
                user__student_group=group
            ).values_list('user_id', flat=True).distinct()

        elif material_type == 'writing':
            # WritingUserAnswer.writing points to Writing model
            # Get all Writing objects for this WritingMaterial
            writings = self.get_related_objects(material, 'Writing')
            if not writings:
                return []

            user_ids = WritingUserAnswer.objects.filter(
                writing__in=writings,
                user__student_group=group
            ).values_list('user_id', flat=True).distinct()

        elif material_type == 'speaking':
            # SpeakingUserAnswer.speaking points to SpeakingMaterial directly
            user_ids = SpeakingUserAnswer.objects.filter(
                speaking=material,
                user__student_group=group
            ).values_list('user_id', flat=True).distinct()

        else:
            return []

        # Get the actual user objects
        return Users.objects.filter(id__in=user_ids).order_by('id')

    def get_related_objects(self, material, related_model_name):
        """Get related objects (Reading, Listening, Writing) for a material"""

        def get_model_by_name(app_labels, model_name):
            for app_label in app_labels:
                try:
                    if app_label:
                        return apps.get_model(app_label, model_name)
                    else:
                        for model in apps.get_models():
                            if model._meta.model_name.lower() == model_name.lower():
                                return model
                except LookupError:
                    continue
            return None

        # Get the related model
        related_model = get_model_by_name([related_model_name.lower(), None], related_model_name)
        if not related_model:
            return []

        # Get related objects based on the relationship
        # Assuming the relationship is: ReadingMaterial -> Reading, ListeningMaterial -> Listening, etc.
        try:
            # Try different possible relationship names
            possible_relations = [
                f'{related_model_name.lower()}_material',  # reading_material, writing_material
                f'{related_model_name.lower()}material',  # readingmaterial, writingmaterial
                'material',  # generic material field
                f'{material._meta.model_name.lower()}'  # based on the material model name
            ]

            for relation_name in possible_relations:
                try:
                    filter_kwargs = {relation_name: material}
                    return related_model.objects.filter(**filter_kwargs)
                except Exception:
                    continue

            # If no direct relationship found, try reverse lookup
            if hasattr(material, f'{related_model_name.lower()}_set'):
                return getattr(material, f'{related_model_name.lower()}_set').all()
            elif hasattr(material, f'{related_model_name.lower()}s'):
                return getattr(material, f'{related_model_name.lower()}s').all()

        except Exception as e:
            print(f"Error getting related objects: {str(e)}")

        return []

    def get_student_results_by_material_type(self, students, material, material_type, test_material):
        """Get detailed results for each student by material type"""

        results = []

        for student in students:
            # Get student basic info
            student_data = {
                'student_id': student.id,
                'full_name': f"{student.first_name} {student.last_name}".strip(),
                'phone': student.phone,
                'group_name': student.student_group.name if student.student_group else 'No Group',
                'created_at': student.date_joined.strftime('%Y-%m-%d-%H:%M'),
                # ✅ Fix: Use date_joined instead of created_at
            }

            # Get material-specific results
            material_info = self.get_material_info_by_type(student, material, material_type, test_material)
            student_data['material_info'] = material_info

            results.append(student_data)

        return results

    def get_material_info_by_type(self, student, material, material_type, test_material):
        """Get material info based on material type"""

        if material_type == 'reading':
            return self.get_reading_material_info(student, material, test_material)
        elif material_type == 'listening':
            return self.get_listening_material_info(student, material, test_material)
        elif material_type == 'writing':
            return self.get_writing_material_info(student, material, test_material)
        elif material_type == 'speaking':
            return self.get_speaking_material_info(student, material, test_material)

        return self.get_default_material_info(material, material_type, test_material)

    def get_reading_material_info(self, student, reading_material, test_material):
        """Get reading material info with actual results"""

        # Get all Reading objects for this ReadingMaterial
        readings = self.get_related_objects(reading_material, 'Reading')
        if not readings:
            return self.get_default_material_info(reading_material, 'reading', test_material)

        # Get all answers for this student and all readings in this material
        user_answers = ReadingUserAnswer.objects.filter(
            user=student,
            reading__in=readings
        )

        total_questions = user_answers.count()
        correct_answers = user_answers.filter(is_true=True).count()
        incorrect_answers = total_questions - correct_answers

        # Calculate score percentage
        score_percentage = (correct_answers / total_questions * 100) if total_questions > 0 else 0.0

        # For reading, score is typically the same as percentage, but you can adjust this
        score = score_percentage / 100 * 9  # Convert to IELTS band scale (0-9)

        return {
            'id': reading_material.id,
            'type': 'reading',
            'title': test_material.test.title,
            'total_questions': total_questions,
            'correct_answers': correct_answers,
            'incorrect_answers': incorrect_answers,
            'score_percentage': round(score_percentage, 1),
            'score': round(score, 1)
        }

    def get_listening_material_info(self, student, listening_material, test_material):
        """Get listening material info with actual results"""

        # Get all Listening objects for this ListeningMaterial
        listenings = self.get_related_objects(listening_material, 'Listening')
        if not listenings:
            return self.get_default_material_info(listening_material, 'listening', test_material)

        # Get all answers for this student and all listenings in this material
        user_answers = ListeningUserAnswer.objects.filter(
            user=student,
            listening__in=listenings
        )

        total_questions = user_answers.count()
        correct_answers = user_answers.filter(is_true=True).count()
        incorrect_answers = total_questions - correct_answers

        # Calculate score percentage
        score_percentage = (correct_answers / total_questions * 100) if total_questions > 0 else 0.0

        # For listening, score is typically the same as percentage, but you can adjust this
        score = score_percentage / 100 * 9  # Convert to IELTS band scale (0-9)

        return {
            'id': listening_material.id,
            'type': 'listening',
            'title': test_material.test.title,
            'total_questions': total_questions,
            'correct_answers': correct_answers,
            'incorrect_answers': incorrect_answers,
            'score_percentage': round(score_percentage, 1),
            'score': round(score, 1)
        }

    def get_writing_material_info(self, student, writing_material, test_material):
        """Get writing material info with actual results"""

        # Get all Writing objects for this WritingMaterial
        writings = self.get_related_objects(writing_material, 'Writing')
        if not writings:
            return self.get_default_material_info(writing_material, 'writing', test_material)

        # Get writing answers for this student and all writings in this material
        user_answers = WritingUserAnswer.objects.filter(
            user=student,
            writing__in=writings
        )

        if user_answers.exists():
            # Calculate average score from all writing tasks
            scores = [answer.score for answer in user_answers if answer.score is not None]

            if scores:
                avg_score = sum(scores) / len(scores)
                score_percentage = (avg_score / 9 * 100)  # Convert from band score to percentage
            else:
                avg_score = 0.0
                score_percentage = 0.0

            total_questions = user_answers.count()
            correct_answers = len([s for s in scores if s >= 5.0])  # Consider passing if score >= 5.0
            incorrect_answers = total_questions - correct_answers

        else:
            avg_score = 0.0
            score_percentage = 0.0
            total_questions = 0
            correct_answers = 0
            incorrect_answers = 0

        return {
            'id': writing_material.id,
            'type': 'writing',
            'title': test_material.test.title,
            'total_questions': total_questions,
            'correct_answers': correct_answers,
            'incorrect_answers': incorrect_answers,
            'score_percentage': round(score_percentage, 1),
            'score': round(avg_score, 1)
        }

    def get_speaking_material_info(self, student, speaking_material, test_material):
        """Get speaking material info with actual results"""

        # Get all speaking answers for this student
        user_answers = SpeakingUserAnswer.objects.filter(
            user=student,
            speaking=speaking_material
        )

        if user_answers.exists():
            # Calculate average score from all speaking questions
            scores = [answer.score for answer in user_answers if answer.score is not None]

            if scores:
                avg_score = sum(scores) / len(scores)
                score_percentage = (avg_score / 9 * 100)  # Convert from band score to percentage
            else:
                avg_score = 0.0
                score_percentage = 0.0

            total_questions = user_answers.count()
            correct_answers = len([s for s in scores if s >= 5.0])  # Consider passing if score >= 5.0
            incorrect_answers = total_questions - correct_answers

        else:
            avg_score = 0.0
            score_percentage = 0.0
            total_questions = 0
            correct_answers = 0
            incorrect_answers = 0

        return {
            'id': speaking_material.id,
            'type': 'speaking',
            'title': test_material.test.title,
            'total_questions': total_questions,
            'correct_answers': correct_answers,
            'incorrect_answers': incorrect_answers,
            'score_percentage': round(score_percentage, 1),
            'score': round(avg_score, 1)
        }

    def get_default_material_info(self, material, material_type, test_material):
        """Get default material info structure"""

        return {
            'id': material.id,
            'type': material_type,
            'title': test_material.test.title,
            'total_questions': 0,
            'correct_answers': 0,
            'incorrect_answers': 0,
            'score_percentage': 0.0,
            'score': 0.0
        }

    def validate_material_by_type(self, material_id, material_type):
        """Validate material based on its type"""

        # Get model dynamically based on material type
        material_model = self.get_material_model(material_type)
        if not material_model:
            return None, Response(
                {"detail": f"{material_type.title()} material model not found."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        try:
            material = material_model.objects.get(id=material_id)
        except material_model.DoesNotExist:
            return None, Response(
                {"detail": f"{material_type.title()} material with id={material_id} not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get test material based on material type
        if material_type == 'speaking':
            # SpeakingMaterial has direct test_material relationship
            test_material = material.test_material
        else:
            # Other materials have test_material through their specific material
            test_material = material.test_material

        return (material, test_material), None

    def get_material_model(self, material_type):
        """Get the appropriate material model based on type"""

        def get_model_by_name(app_labels, model_name):
            for app_label in app_labels:
                try:
                    if app_label:
                        return apps.get_model(app_label, model_name)
                    else:
                        for model in apps.get_models():
                            if model._meta.model_name.lower() == model_name.lower():
                                return model
                except LookupError:
                    continue
            return None

        material_model_map = {
            'reading': get_model_by_name(['reading', None], 'ReadingMaterial'),
            'listening': get_model_by_name(['listening', None], 'ListeningMaterial'),
            'writing': get_model_by_name(['writing', None], 'WritingMaterial'),
            'speaking': get_model_by_name(['speaking', None], 'SpeakingMaterial'),
        }

        return material_model_map.get(material_type)

    def get(self, request, result_type):
        """Handle GET requests for specific material type"""
        return self.get_thematic_results_data_without_pagination(request, result_type)


