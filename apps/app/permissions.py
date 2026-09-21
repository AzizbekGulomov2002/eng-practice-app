from rest_framework import permissions
from apps.app.models import StudentGroup, Test, TestAccept, TestMaterial
from rest_framework.permissions import BasePermission
from django.utils import timezone
import logging
logger = logging.getLogger(__name__)

class IsTestAcceptance(BasePermission):
    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            logger.debug("❌ TestAcceptance: Unauthenticated user")
            return False

        if user.role == "Teacher":
            logger.debug("🎓 TestAcceptance: Teacher access granted")
            return True

        # For students, check if they have any active test acceptances
        active_accepts = TestAccept.objects.all()
        
        for accept in active_accepts:
            if accept.is_user_allowed(user):
                logger.debug(f"✅ TestAcceptance: User {user.id} has access via TestAccept {accept.id}")
                return True

        logger.debug(f"❌ TestAcceptance: User {user.id} has no valid TestAccept")
        return False

    def has_object_permission(self, request, view, obj):
        user = request.user
        
        if not user or not user.is_authenticated:
            return False
            
        if user.role == "Teacher":
            return True

        # Check if user has access to this specific test
        if hasattr(obj, 'test'):  # For TestMaterial objects
            test = obj.test
        elif isinstance(obj, Test):  # For Test objects
            test = obj
        else:
            return False

        # Find accepts that include this test
        test_material_ids = TestMaterial.objects.filter(
            test=test
        ).values_list('id', flat=True)
        
        relevant_accepts = TestAccept.objects.filter(
            test_material__id__in=test_material_ids
        ).distinct()
        
        for accept in relevant_accepts:
            if accept.is_user_allowed(user):
                return True
        
        return False


class IsTeacher(permissions.BasePermission):
    def has_permission(self, request, view):
        if getattr(view, 'swagger_fake_view', False):
            return True
        return bool(request.user and request.user.is_authenticated and getattr(request.user, 'role', None) == 'Teacher')


