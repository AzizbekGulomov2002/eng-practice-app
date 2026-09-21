from rest_framework import serializers
from django.contrib.auth import authenticate
from apps.app.models import TestMaterial, Users, Test
import re

class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    groups = serializers.SerializerMethodField()

    class Meta:
        model = Users
        fields = (
            'id',
            'username',
            'full_name',
            'phone',
            'role',
            'groups',
        )
        extra_kwargs = {
            'username': {'required': True},
        }
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()
    def get_groups(self, obj):
        return None

class AuthTokenSerializer(serializers.Serializer):
    username = serializers.CharField(label="Username")
    password = serializers.CharField(label="Password", style={'input_type': 'password'}, trim_whitespace=False)

    
class MaterialSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    type = serializers.CharField()
    title = serializers.CharField()


class TestMaterialSerializer(serializers.ModelSerializer):
    materials = serializers.SerializerMethodField()
    test_type = serializers.CharField(source="test.test_type", read_only=True)

    class Meta:
        model = TestMaterial
        fields = ["id", "title", "test_type", "materials"]

    def extract_activity_number(self, title):
        """Extract Activity number from title, return 999999 if not found"""
        if not title:
            return 999999
        match = re.search(r"Activity\s*(\d+)", title)
        if match:
            return int(match.group(1))
        return 999999  # Put non-Activity items at the end

    def get_materials(self, obj):
        materials = []

        # Reading - Use the correct related_name from ReadingMaterial model
        # In ReadingMaterial: test_material = ForeignKey("app.TestMaterial", related_name="reading_materials")
        if hasattr(obj, 'reading_materials') and obj.reading_materials.exists():
            readings = list(obj.reading_materials.values("id", "title"))
            for idx, r in enumerate(readings, start=1):
                materials.append({
                    "id": r["id"],
                    "type": "reading",
                    "title": r["title"] if r["title"] else f"Reading passage {idx}"
                })

        # For other materials, we need to check the actual related names in your models
        # Since I don't see the complete models for listening, writing, speaking,
        # I'll show you the pattern to fix them:

        # If ListeningMaterial has: test_material = ForeignKey(TestMaterial, related_name="listening_materials")
        if hasattr(obj, 'listening_materials') and obj.listening_materials.exists():
            listenings = list(obj.listening_materials.values("id", "title"))
            for idx, l in enumerate(listenings, start=1):
                materials.append({
                    "id": l["id"],
                    "type": "listening",
                    "title": l["title"] if l["title"] else f"Listening part {idx}"
                })
        
        # Alternative: if no explicit related_name is set, Django creates default reverse relation
        # For model named ListeningMaterial, it would be listeningmaterial_set
        elif hasattr(obj, 'listeningmaterial_set') and obj.listeningmaterial_set.exists():
            listenings = list(obj.listeningmaterial_set.values("id", "title"))
            for idx, l in enumerate(listenings, start=1):
                materials.append({
                    "id": l["id"],
                    "type": "listening",
                    "title": l["title"] if l["title"] else f"Listening part {idx}"
                })

        # Writing - Check your WritingMaterial model for the correct related_name
        if hasattr(obj, 'writing_materials') and obj.writing_materials.exists():
            writings = list(obj.writing_materials.values("id", "title"))
            for idx, w in enumerate(writings, start=1):
                materials.append({
                    "id": w["id"],
                    "type": "writing",
                    "title": w["title"] if w["title"] else f"Writing task {idx}"
                })
        elif hasattr(obj, 'writingmaterial_set') and obj.writingmaterial_set.exists():
            writings = list(obj.writingmaterial_set.values("id", "title"))
            for idx, w in enumerate(writings, start=1):
                materials.append({
                    "id": w["id"],
                    "type": "writing",
                    "title": w["title"] if w["title"] else f"Writing task {idx}"
                })

        # Speaking - Check your SpeakingMaterial model for the correct related_name  
        if hasattr(obj, 'speaking_materials') and obj.speaking_materials.exists():
            speakings = list(obj.speaking_materials.values("id", "title"))
            for idx, s in enumerate(speakings, start=1):
                materials.append({
                    "id": s["id"],
                    "type": "speaking",
                    "title": s["title"] if s["title"] else f"Speaking part {idx}"
                })
        elif hasattr(obj, 'speakingmaterial_set') and obj.speakingmaterial_set.exists():
            speakings = list(obj.speakingmaterial_set.values("id", "title"))
            for idx, s in enumerate(speakings, start=1):
                materials.append({
                    "id": s["id"],
                    "type": "speaking",
                    "title": s["title"] if s["title"] else f"Speaking part {idx}"
                })

        # 🎯 Sort materials based on test type
        if obj.test and obj.test.test_type == 'Thematic':
            # Sort by Activity number for Thematic tests
            materials.sort(key=lambda m: self.extract_activity_number(m.get('title', '')))
        elif obj.test and obj.test.test_type == 'Mock':
            # Sort by type order for Mock tests: listening, reading, writing, speaking
            type_order = {"listening": 1, "reading": 2, "writing": 3, "speaking": 4}
            materials.sort(key=lambda m: type_order.get(m.get('type', ''), 99))

        return materials


class TestSerializer(serializers.ModelSerializer):
    sections = serializers.SerializerMethodField()
    start_test = serializers.SerializerMethodField()
    start_test_id = serializers.SerializerMethodField()

    class Meta:
        model = Test
        fields = [
            "id",
            "title",
            "test_type",
            "test_number",
            "date",
            "sections",
            "start_test",
            "start_test_id",
        ]

    def to_representation(self, instance):
        """
        Remove start_test and start_test_id for Thematic tests
        """
        data = super().to_representation(instance)

        # Remove start_test fields only for Thematic tests
        if instance.test_type == 'Thematic':
            data.pop('start_test', None)
            data.pop('start_test_id', None)

        return data

    def get_sections(self, obj):
        request = self.context.get('request')
        user = request.user if request and request.user.is_authenticated else None

        if user and user.role == "Teacher":
            test_materials = obj.testmaterial_set.all()
        elif user and user.is_authenticated:
            allowed_material_ids = self.get_user_allowed_material_ids(user)
            test_materials = obj.testmaterial_set.filter(id__in=allowed_material_ids)
        else:
            test_materials = obj.testmaterial_set.none()

        # Sort sections in order: listening, reading, writing, speaking
        # Only apply special sorting for Mock tests
        if obj.test_type == "Mock":
            ordered_materials = sorted(
                test_materials,
                key=lambda x: self.get_section_order(x)
            )
        else:
            ordered_materials = test_materials
        return TestMaterialSerializer(ordered_materials, many=True, context=self.context).data

    def get_section_order(self, test_material):
        """Get the order priority for Mock test sections"""
        if not test_material.title:
            return 99
        
        title_lower = test_material.title.lower()
        
        # Check for section type in title
        if 'listening' in title_lower:
            return 1
        elif 'reading' in title_lower:
            return 2
        elif 'writing' in title_lower:
            return 3
        elif 'speaking' in title_lower:
            return 4
        else:
            return 99

    def get_start_test(self, obj):
        if obj.test_type == "Mock":
            return "Listening"
        else:
            sections = self.get_sections(obj)
            if sections:
                first_section = sections[0]
                if 'materials' in first_section and first_section['materials']:
                    first_material = first_section['materials'][0]
                    return first_material['type'].capitalize()
            return None

    def get_start_test_id(self, obj):
        if obj.test_type == "Mock":
            sections = self.get_sections(obj)

            for section in sections:
                if 'materials' in section:
                    for material in section['materials']:
                        if material['type'] == 'listening':
                            return material['id']

            if sections and sections[0].get('materials'):
                return sections[0]['materials'][0]['id']

            return None
        else:
            sections = self.get_sections(obj)
            if sections and sections[0].get('materials'):
                return sections[0]['materials'][0]['id']

            return None

    def get_user_allowed_material_ids(self, user):
        try:
            from apps.app.models import TestAccept

            direct_accepts = TestAccept.objects.filter(students=user)

            group_accepts = TestAccept.objects.none()
            if hasattr(user, 'student_group') and user.student_group:
                group_accepts = TestAccept.objects.filter(groups=user.student_group)

            accepts = direct_accepts.union(group_accepts)

            allowed_material_ids = []
            for accept in accepts:
                if accept.is_user_allowed(user):
                    material_ids = list(accept.test_material.values_list("id", flat=True))
                    allowed_material_ids.extend(material_ids)

            return list(set(allowed_material_ids))

        except Exception as e:
            return []


