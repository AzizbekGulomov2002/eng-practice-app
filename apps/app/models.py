import logging
logger = logging.getLogger(__name__)
import ipaddress
from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission, UserManager as DjangoUserManager
from rest_framework.exceptions import ValidationError
import random
import string
from django.utils import timezone
from django.urls import reverse

class StudentGroup(models.Model):
    name = models.CharField(max_length=100, verbose_name="Group Name")
    is_active = models.BooleanField(default=True, verbose_name="Active Group")
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Student groups"
        verbose_name_plural = "Student groups"


class UsersManager(DjangoUserManager):
    def _unique_placeholder_phone(self, username):
        digits = "".join(ch for ch in (username or "") if ch.isdigit()) or str(abs(hash(username)) % 10**9)
        phone = ("+000" + digits)[:15]
        n = 0
        while self.model.objects.filter(phone=phone).exists():
            n += 1
            phone = ("+000" + digits + str(n))[:15]
        return phone

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", "Teacher")
        extra_fields.setdefault("first_name", extra_fields.get("first_name") or "Admin")
        extra_fields.setdefault("last_name", extra_fields.get("last_name") or "User")
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if not extra_fields.get("phone"):
            extra_fields["phone"] = self._unique_placeholder_phone(username)
        return super().create_superuser(username, email or "", password, **extra_fields)


class Users(AbstractUser):
    ROLE_CHOICES = [
        ('Teacher', 'Teacher'),
        ('Student', 'Student'),
    ]
    groups = models.ManyToManyField(
        Group,
        related_name='customuser_set',
        blank=True,
        verbose_name='Groups',
        help_text='Groups in Students.'
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='customuser_set',
        blank=True,
        verbose_name='Permissions',
        help_text='Permissions for Students.'
    )

    
    first_name = models.CharField(max_length=50, verbose_name="First Name")
    last_name = models.CharField(max_length=50, verbose_name="Last Name")
    phone = models.CharField(max_length=15, unique=True, verbose_name="Phone Number")
    role = models.CharField(
        max_length=10, 
        choices=ROLE_CHOICES, 
        default='Student',
        verbose_name="Rol"
    )
    is_parse = models.BooleanField(
        default=True,
        verbose_name="Parse Questions",
        help_text="If False, questions in reading and listening will be displayed as-is without parsing"
    )
    objects = UsersManager()
    
    def generate_password(self):
        return ''.join(random.choices(string.digits, k=8))
    
    
    REQUIRED_FIELDS = []

    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.role})"
    
    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"


class Test(models.Model):
    TEST_TYPE_CHOICES = (
        ('Mock', 'Mock'),
        ('Thematic', 'Thematic')
    )
    title = models.CharField(max_length=300, null=True, blank=True)
    test_number = models.CharField(
        max_length=60,
        unique=True,
        editable=False,
        blank=True,
    )
    test_type   = models.CharField(max_length=25, choices=TEST_TYPE_CHOICES)
    date=models.DateField(auto_now_add=True)
    
    def __str__(self):
        if self.title:
            return self.title
        elif self.test_number:
            return f"Test {self.test_number}"
        return "Unnamed Test"

    
    def save(self, *args, **kwargs):
        if not self.test_number:
            created = self.date or timezone.now().date()
            date_str = created.strftime("%Y%m%d")
            prefix = f"{self.test_type}-{date_str}-"
            existing_count = (
                Test.objects
                .filter(test_number__startswith=prefix)
                .count()
            )
            seq = f"{existing_count + 1:03d}"
            self.test_number = f"{prefix}{seq}"

        super().save(*args, **kwargs)


class TestMaterial(models.Model):
    test = models.ForeignKey(Test, on_delete=models.CASCADE)
    title = models.CharField(max_length=300,blank=True, null=True)
    audio = models.FileField(upload_to='listening_audios/', null=True, blank=True)
    is_view = models.BooleanField(default=False, help_text="Is view answer for mock test user or not")
    class Meta:
        verbose_name='Test Material'
        verbose_name_plural='Test Materials'

    def __str__(self):
        return f"{self.title} ({self.test.title})"


class TestAccept(models.Model):
    groups = models.ManyToManyField("StudentGroup", blank=True)
    students = models.ManyToManyField(
        "Users",
        blank=True,
        limit_choices_to={'role': 'Student'}
    )
    test_material = models.ManyToManyField("TestMaterial", related_name='accepted_by')

    # These will be automatically populated when test_material is added
    listening_materials = models.ManyToManyField("listening.ListeningMaterial", blank=True)
    reading_materials = models.ManyToManyField("reading.ReadingMaterial", blank=True)
    writing_materials = models.ManyToManyField("writing.WritingMaterial", blank=True)
    speaking_materials = models.ManyToManyField("speaking.SpeakingMaterial", blank=True)

    deadline_from = models.DateTimeField(null=True, blank=True)
    deadline_to = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Test Acceptance'
        verbose_name_plural = 'Test Acceptances'

    def __str__(self):
        tests = [tm.test.test_number for tm in self.test_material.all()]
        return f"Tests: {', '.join(tests)}" if tests else "No Tests"

    def is_deadline_active(self) -> bool:
        now = timezone.now()
        
        # Agar deadline lar bo'lmasa, har doim active
        if not self.deadline_from and not self.deadline_to:
            return True
        
        # Faqat boshlanish deadline bor
        if self.deadline_from and not self.deadline_to:
            return now >= self.deadline_from
        
        # Faqat tugash deadline bor
        if self.deadline_to and not self.deadline_from:
            return now <= self.deadline_to
        
        # Ikkala deadline ham bor
        if self.deadline_from and self.deadline_to:
            return self.deadline_from <= now <= self.deadline_to
        
        return False

    def is_user_allowed(self, user) -> bool:
        """Check if a specific user has access to this acceptance"""
        try:
            # Deadline tekshirish
            if not self.is_deadline_active():
                logger.debug(f"❌ TestAccept {self.id}: Deadline not active for user {user.id}")
                return False
            
            # To'g'ridan-to'g'ri student sifatida qo'shilgan mi?
            if self.students.filter(id=user.id).exists():
                logger.debug(f"✅ TestAccept {self.id}: User {user.id} found in direct students")
                return True

            return False
            
        except Exception as e:
            logger.error(f"💥 Error in TestAccept.is_user_allowed for ID {self.id}, user {user.id}: {str(e)}")
            return False

    def get_all_allowed_users(self):
        """Get all users who have access through this acceptance"""
        allowed_users = set()
        
        # Add directly assigned students
        allowed_users.update(self.students.filter(is_active=True, role='Student'))
        return list(allowed_users)



class AllowedIP(models.Model):
    users = models.ManyToManyField(
        "Users",
        blank=True,
        help_text="Agar user tanlansa, IP va device UUID cheklovi yo'q - istalgan device dan kirishi mumkin"
    )
    ip_address = models.GenericIPAddressField(blank=True, null=True, help_text="IP address yoki subnet")
    device_uuid = models.CharField(max_length=255, blank=True, null=True, 
                                   help_text="Hardware UUID (Device identifier)")
    description = models.CharField(max_length=200, blank=True, null=True,
                                  help_text="Bu IP/Device/User haqida izoh")
    is_active = models.BooleanField(default=True, help_text="Faol yoki faol emas")

    def clean(self):
        if self.ip_address:
            try:
                ipaddress.ip_network(self.ip_address, strict=False)
            except ValueError:
                raise ValidationError({'ip_address': 'Invalid IP address or network format'})

    def __str__(self):
        parts = []
        
        if self.users.exists():
            users_str = ", ".join([user.username for user in self.users.all()[:3]])
            if self.users.count() > 3:
                users_str += f" (+{self.users.count() - 3} more)"
            parts.append(f"Users: {users_str}")
        
        if self.ip_address:
            parts.append(f"IP: {self.ip_address}")
            
        if self.device_uuid:
            parts.append(f"Device: {self.device_uuid[:8]}...")
            
        if not parts:
            parts.append("Empty AllowedIP")
            
        status = "Active" if self.is_active else "Inactive"
        return f"{' | '.join(parts)} ({status})"

    class Meta:
        unique_together = [
            ['ip_address', 'device_uuid'],
        ]
        verbose_name = "Allowed IP/Device"
        verbose_name_plural = "Allowed IPs/Devices"

    @classmethod
    def is_ip_in_allowed_networks(cls, client_ip):
        """Check if client IP is in any of the allowed networks"""
        if not client_ip or client_ip == "Unknown":
            return False
            
        try:
            client_ip_obj = ipaddress.ip_address(client_ip)
            
            for allowed_ip in cls.objects.filter(ip_address__isnull=False, is_active=True):
                try:
                    network = ipaddress.ip_network(allowed_ip.ip_address, strict=False)
                    if client_ip_obj in network:
                        logger.debug(f"IP {client_ip} matches network {allowed_ip.ip_address}")
                        return True
                except ValueError:
                    continue
                    
        except ValueError:
            logger.debug(f"Invalid IP format: {client_ip}")
            
        return False




