from rest_framework.decorators import action
from rest_framework import generics, permissions
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.app.middleware import AllowedIPMixin, IsAllowedIP
from apps.app.models import AllowedIP, TestAccept, TestMaterial, Test
from apps.app.permissions import IsTestAcceptance
from apps.app.serializers import TestMaterialSerializer, UserSerializer, AuthTokenSerializer,TestSerializer
from apps.app.pagination import BasePaginationView, TenPaginationView
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.db.models import IntegerField, Value, Case, When, F
from django.db.models.functions import Cast, Substr, Replace, Length
import re


class MeAPIView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get(self, request):
        serializer = self.serializer_class(request.user)
        return Response(serializer.data)

from django.contrib.auth import authenticate

class CustomAuthToken(ObtainAuthToken):
    serializer_class = AuthTokenSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data.get('username')
        password = serializer.validated_data.get('password')

        user = authenticate(request=request, username=username, password=password)
        if user is None:
            return Response({'detail': 'Unable to log in with provided credentials.'},
                            status=status.HTTP_401_UNAUTHORIZED)

        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'username': user.username,
            'role': user.role,
        }, status=status.HTTP_200_OK)
     

import logging

logger = logging.getLogger(__name__)

class TestListView(AllowedIPMixin, TenPaginationView):
    permission_classes = []
    serializer_class = TestSerializer
    search_fields = ["title", "test_number"]

    def paginate_list(self, items_list, request):
        """Paginate a Python list instead of a queryset"""
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', self.page_size))
        
        start = (page - 1) * page_size
        end = start + page_size
        
        total_count = len(items_list)
        results = items_list[start:end]
        
        return {
            'count': total_count,
            'next': page + 1 if end < total_count else None,
            'previous': page - 1 if page > 1 else None,
            'results': results,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size
        }

    def get(self, request, *args, **kwargs):
        user = request.user if request.user.is_authenticated else None
        ip = self.get_client_ip(request)
        device_uuid = self.get_device_uuid(request)
        
        logger.debug(f"🚀 TestListView: User={user.id if user else 'Anonymous'}, IP={ip}, Device={device_uuid}")

        try:
            # 🎓 Teachers - Full access to all tests
            if user and user.is_authenticated and user.role == "Teacher":
                queryset = Test.objects.all().order_by('-date', '-id')
                logger.debug(f"🎓 Teacher access: {queryset.count()} tests available")
                
            # 👨‍🎓 Students (authenticated) - Check AllowedIP + TestAccept
            elif user and user.is_authenticated and user.role == "Student":
                ip_access_granted = self.is_user_or_ip_allowed(request)
                
                if not ip_access_granted:
                    queryset = Test.objects.none()
                    logger.debug("❌ Student: IP/User access denied - no tests")
                else:
                    queryset = self.get_user_allowed_tests(user)
                    logger.debug(f"👨‍🎓 Student access granted: {queryset.count()} tests via TestAccept")
                    
            # 👤 Anonymous users - IP-based access only
            elif not user or not user.is_authenticated:
                ip_access_granted = self.is_anonymous_ip_allowed(request)
                
                if ip_access_granted:
                    # Anonymous users get all tests if IP is allowed
                    queryset = Test.objects.all().order_by('-date', '-id')
                    logger.debug(f"👤 Anonymous IP access granted: {queryset.count()} tests available")
                else:
                    queryset = Test.objects.none()
                    logger.debug("❌ Anonymous IP access denied - no tests")
            else:
                queryset = Test.objects.none()
                logger.debug("❌ Unknown user type - no tests")
                        
        except Exception as e:
            logger.error(f"💥 TestListView error: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            queryset = Test.objects.none()

        # Filter by test type if specified
        test_type = request.query_params.get("test_type")
        if test_type:
            original_count = queryset.count()
            queryset = queryset.filter(test_type__iexact=test_type)
            logger.debug(f"🔽 Filtered by test_type '{test_type}': {original_count} → {queryset.count()} tests")
            
            # 🎯 Special ordering for Thematic tests by Activity number
            if test_type.lower() == 'thematic':
                # Extract Activity number from title (e.g., "Activity 111 (C14T1 Passage 2)" -> 111)
                # We'll use Python-side sorting since regex extraction in SQL can be database-specific
                logger.debug("🔢 Applying Activity number ordering for Thematic tests")

        try:
            filtered_queryset = self.filter_queryset(queryset, request)
            
            # 🎯 Apply Activity number sorting for Thematic tests
            if test_type and test_type.lower() == 'thematic':
                # Convert to list and sort by Activity number
                filtered_list = list(filtered_queryset)
                
                def extract_activity_number(test):
                    """Extract Activity number from title, return 999999 if not found"""
                    match = re.search(r"Activity\s*(\d+)", test.title)
                    if match:
                        return int(match.group(1))
                    return 999999  # Put non-Activity items at the end
                
                filtered_list.sort(key=extract_activity_number)
                logger.debug(f"🔢 Sorted {len(filtered_list)} Thematic tests by Activity number")
                
                # Paginate the sorted list
                paginated_data = self.paginate_list(filtered_list, request)
            else:
                paginated_data = self.paginate_queryset(filtered_queryset, request)
            
            serializer = self.serializer_class(
                paginated_data["results"], 
                many=True, 
                context={'request': request}
            )
            paginated_data["results"] = serializer.data
            
            logger.debug(f"📄 Final response: {len(paginated_data['results'])} tests on page {paginated_data.get('page', 1)}")
            return Response(paginated_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"💥 TestListView serialization error: {str(e)}")
            return Response(
                {"error": "Internal server error", "detail": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get_user_allowed_tests(self, user):
        """Get tests that user can access through TestAccept"""
        try:
            logger.debug(f"🔍 Getting TestAccept permissions for user {user.id}")
            
            # Get all TestAccept objects with prefetch
            all_accepts = TestAccept.objects.prefetch_related(
                'test_material__test', 'groups', 'students'
            ).all()
            
            logger.debug(f"📊 Found {all_accepts.count()} TestAccept objects")
            
            allowed_test_ids = set()
            
            for accept in all_accepts:
                logger.debug(f"🔍 Checking TestAccept {accept.id}")
                
                if accept.is_user_allowed(user):
                    test_ids = accept.test_material.values_list('test_id', flat=True)
                    test_ids_list = list(test_ids)
                    allowed_test_ids.update(test_ids_list)
                    logger.debug(f"✅ TestAccept {accept.id} allowed - added {len(test_ids_list)} test IDs: {test_ids_list}")
                else:
                    logger.debug(f"❌ TestAccept {accept.id} not allowed for user")
            
            logger.debug(f"📊 Total allowed test IDs: {len(allowed_test_ids)} → {list(allowed_test_ids)}")
            
            if not allowed_test_ids:
                logger.debug("❌ No TestAccept permissions found")
                return Test.objects.none()
            
            # Get tests
            queryset = Test.objects.filter(
                id__in=allowed_test_ids
            ).distinct().order_by('-date', '-id')
            
            logger.debug(f"📄 Final TestAccept queryset: {queryset.count()} tests")
            
            # Debug: Show test details
            for test in queryset[:3]:
                logger.debug(f"📋 Test: {test.id} - {test.title or test.test_number}")
            
            return queryset
            
        except Exception as e:
            logger.error(f"💥 Error in get_user_allowed_tests: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return Test.objects.none()



class TestMaterialistListView(AllowedIPMixin, BasePaginationView):
    permission_classes = []
    serializer_class = TestMaterialSerializer
    queryset = TestMaterial.objects.all()
    search_fields = ["title", "test__test_type"]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter("search", openapi.IN_QUERY, description="Search by title.", type=openapi.TYPE_STRING),
            openapi.Parameter("test_type", openapi.IN_QUERY, description="Filter by test type (Mock or Thematic).", type=openapi.TYPE_STRING, enum=["Mock", "Thematic"]),
            openapi.Parameter("page", openapi.IN_QUERY, description="Page number for pagination.", type=openapi.TYPE_INTEGER),
            openapi.Parameter("page_size", openapi.IN_QUERY, description="Number of items per page.", type=openapi.TYPE_INTEGER),
        ]
    )
    def get(self, request, *args, **kwargs):
        device_uuid = self.get_device_uuid(request)
        ip = self.get_client_ip(request)
        user = request.user if request.user.is_authenticated else None

        try:
            if user and user.is_authenticated and user.role == "Teacher":
                queryset = TestMaterial.objects.all()
            elif not AllowedIP.objects.exists():
                queryset = TestMaterial.objects.none()
            else:
                access_granted = self.is_user_or_ip_allowed(request)
                
                if access_granted:
                    if user and user.is_authenticated:
                        queryset = self.get_user_allowed_test_materials(user)
                    else:
                        queryset = TestMaterial.objects.none()
                else:
                    queryset = TestMaterial.objects.none()
                        
        except Exception as e:
            queryset = TestMaterial.objects.none()

        test_type = request.query_params.get("test_type")
        if test_type:
            queryset = queryset.filter(test__test_type__iexact=test_type)

        try:
            filtered_queryset = self.filter_queryset(queryset, request)
            paginated_data = self.paginate_queryset(filtered_queryset, request)
            serializer = self.serializer_class(paginated_data["results"], many=True)
            paginated_data["results"] = serializer.data
            
            return Response(paginated_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": "Internal server error", "detail": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get_user_allowed_test_materials(self, user):
        try:
            direct_accepts = TestAccept.objects.filter(students=user)
            
            group_accepts = TestAccept.objects.none()
            if hasattr(user, 'student_group') and user.student_group:
                group_accepts = TestAccept.objects.filter(groups=user.student_group)
            
            accepts = direct_accepts.union(group_accepts)
            
            # Faqat ruxsat etilgan test material ID larini olish
            allowed_material_ids = []
            for accept in accepts:
                if accept.is_user_allowed(user):
                    # To'g'ridan-to'g'ri TestMaterial ID larni olish
                    material_ids = list(accept.test_material.values_list("id", flat=True))
                    allowed_material_ids.extend(material_ids)
            
            allowed_material_ids = list(set(allowed_material_ids))
            
            return TestMaterial.objects.filter(id__in=allowed_material_ids).distinct()
            
        except Exception as e:
            return TestMaterial.objects.none()


