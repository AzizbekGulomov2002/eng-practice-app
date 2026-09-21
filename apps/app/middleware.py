import logging
from django.db.models import Q
from rest_framework.permissions import BasePermission
logger = logging.getLogger("student_actions")

class AllowedIPMixin:
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()

        real_ip = request.META.get("HTTP_X_REAL_IP")
        if real_ip:
            return real_ip.strip()

        return request.META.get("REMOTE_ADDR", "Unknown")

    def get_device_uuid(self, request):
        uuid_headers = [
            'HTTP_X_DEVICE_UUID',
            'HTTP_DEVICE_UUID', 
            'HTTP_X_DEVICE_ID',
            'HTTP_DEVICE_ID',
            'HTTP_UUID',
        ]
        
        for header in uuid_headers:
            device_uuid = request.META.get(header)
            if device_uuid:
                return device_uuid.strip()
        
        device_uuid = request.GET.get('device_uuid')
        if device_uuid:
            return device_uuid.strip()
            
        if request.method == 'POST':
            device_uuid = request.POST.get('device_uuid')
            if device_uuid:
                return device_uuid.strip()
        
        return None

    def is_user_or_ip_allowed(self, request):
        from apps.app.models import AllowedIP
        
        device_uuid = self.get_device_uuid(request)
        ip = self.get_client_ip(request)
        user = request.user if request.user.is_authenticated else None
        
        logger.debug(f"Access check: user={user.id if user else 'None'}, ip={ip}, device={device_uuid}")
        
        # Teacher - har doim full access
        if user and user.is_authenticated and user.role == "Teacher":
            logger.debug("✅ Access granted: Teacher role")
            return True
        
        # AllowedIP mavjudligini tekshirish
        total_allowed_ips = AllowedIP.objects.filter(is_active=True).count()
        if total_allowed_ips == 0:
            logger.debug("❌ No active AllowedIP objects exist - denying access")
            return False
        
        logger.debug(f"📊 Found {total_allowed_ips} active AllowedIP objects")
        
        # 🔥 PRIORITY 1: User-based access (IP-independent)
        if user and user.is_authenticated:
            user_allowed = AllowedIP.objects.filter(users=user, is_active=True)
            if user_allowed.exists():
                logger.debug(f"✅ Access granted: User {user.id} found in AllowedIP (IP-independent access)")
                return True
            else:
                logger.debug(f"ℹ️ User {user.id} not found in AllowedIP users")
        
        # 🔥 PRIORITY 2: IP-based access
        if ip and ip != "Unknown":
            # Exact IP match
            ip_allowed = AllowedIP.objects.filter(ip_address=ip, is_active=True)
            logger.debug(f"🔍 Checking exact IP '{ip}': found {ip_allowed.count()} matches")
            
            if ip_allowed.exists():
                logger.debug(f"✅ Access granted: IP {ip} found in AllowedIP")
                return True
            
            # Subnet/network check
            if AllowedIP.is_ip_in_allowed_networks(ip):
                logger.debug(f"✅ Access granted: IP {ip} found in allowed networks")
                return True
            else:
                logger.debug(f"ℹ️ IP {ip} not found in allowed networks")
        
        # 🔥 PRIORITY 3: Device UUID access
        if device_uuid:
            device_allowed = AllowedIP.objects.filter(device_uuid=device_uuid, is_active=True)
            logger.debug(f"🔍 Checking device '{device_uuid}': found {device_allowed.count()} matches")
            
            if device_allowed.exists():
                logger.debug(f"✅ Access granted: Device UUID {device_uuid} found")
                return True
            else:
                logger.debug(f"ℹ️ Device UUID {device_uuid} not found")
        
        logger.debug("❌ Access denied: No matching AllowedIP found")
        return False

    def is_anonymous_ip_allowed(self, request):
        """Anonymous users uchun faqat IP/Device-based access"""
        from apps.app.models import AllowedIP
        
        ip = self.get_client_ip(request)
        device_uuid = self.get_device_uuid(request)
        
        logger.debug(f"Anonymous access check: ip={ip}, device={device_uuid}")
        
        # AllowedIP mavjudligini tekshirish
        total_allowed_ips = AllowedIP.objects.filter(is_active=True).count()
        if total_allowed_ips == 0:
            logger.debug("❌ No active AllowedIP objects - denying anonymous access")
            return False
        
        logger.debug(f"📊 Found {total_allowed_ips} active AllowedIP objects")
        
        # Debug: Show first few AllowedIPs
        for allowed_ip in AllowedIP.objects.filter(is_active=True)[:3]:
            logger.debug(f"🔍 AllowedIP {allowed_ip.id}: ip='{allowed_ip.ip_address}', device='{allowed_ip.device_uuid}'")
        
        # IP address check
        if ip and ip != "Unknown":
            ip_matches = AllowedIP.objects.filter(ip_address=ip, is_active=True)
            logger.debug(f"🔍 Looking for exact IP '{ip}': found {ip_matches.count()} matches")
            
            if ip_matches.exists():
                logger.debug(f"✅ Anonymous access granted: IP {ip} found")
                return True
            
            # Subnet check
            if AllowedIP.is_ip_in_allowed_networks(ip):
                logger.debug(f"✅ Anonymous access granted: IP {ip} in allowed networks")
                return True
        
        # Device UUID check
        if device_uuid:
            device_matches = AllowedIP.objects.filter(device_uuid=device_uuid, is_active=True)
            logger.debug(f"🔍 Looking for device '{device_uuid}': found {device_matches.count()} matches")
            
            if device_matches.exists():
                logger.debug(f"✅ Anonymous access granted: Device {device_uuid} found")
                return True
        
        logger.debug("❌ Anonymous access denied: No matching IP/Device found")
        return False

    def log_allowed_ips(self):
        from apps.app.models import AllowedIP
        return AllowedIP.objects.filter(is_active=True)


class IsAllowedIP(AllowedIPMixin, BasePermission):
    def has_permission(self, request, view):
        user = request.user
        
        # Teacher - har doim ruxsat
        if user and user.is_authenticated and user.role == "Teacher":
            logger.debug("🎓 Permission granted: Teacher role")
            return True
            
        # AllowedIP tekshirish
        ip_allowed = self.is_user_or_ip_allowed(request)
        
        if not ip_allowed:
            logger.debug("❌ Permission denied: User/IP not in AllowedIP")
            return False
            
        logger.debug("✅ Permission granted: User/IP found in AllowedIP")
        return True


class DeviceUUIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        stored_uuid = None
        if hasattr(request, 'session'):
            stored_uuid = request.session.get('device_uuid')
        
        current_uuid = (
            request.META.get('HTTP_X_DEVICE_UUID') or
            request.META.get('HTTP_DEVICE_UUID') or
            request.GET.get('device_uuid') or
            request.POST.get('device_uuid')
        )
        
        if current_uuid:
            current_uuid = current_uuid.strip()
            request.device_uuid = current_uuid
            
            if hasattr(request, 'session'):
                request.session['device_uuid'] = current_uuid
                
        elif stored_uuid:
            request.device_uuid = stored_uuid
        else:
            request.device_uuid = None

        response = self.get_response(request)
        return response


class StudentActionLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            if user.role == "Student":
                logger.info(f"Student {user} called {request.method} {request.path}")
            elif user.role == "Teacher":
                logger.info(f"Teacher {user} called {request.method} {request.path}")
        return response

