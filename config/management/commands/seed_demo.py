import math
import shutil
import struct
import subprocess
import wave
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand

from apps.app.models import Test, TestAccept, TestMaterial, Users
from apps.listening.models import Listening, ListeningAnswer, ListeningMaterial, ListeningUserAnswer
from apps.reading.models import Reading, ReadingAnswer, ReadingMaterial, ReadingUserAnswer
from apps.speaking.models import Speaking, SpeakingAnswer, SpeakingMaterial, SpeakingUserAnswer
from apps.web.utils import build_quiz_html
from apps.writing.models import Writing, WritingAnswer, WritingMaterial, WritingUserAnswer


READING_TEXT = """
<p>Cities around the world are looking for practical ways to become healthier and more sustainable. One idea that appears again and again is ecological intelligence: the ability to understand how everyday actions affect the environment and to choose options that support long-term wellbeing.</p>
<p>Research shows that people learn this kind of thinking more easily when lessons are connected to real life. Students who study language or science through topics such as clean air, local food, and green transport often remember information better than those who only memorise abstract facts. Walking or cycling instead of driving, for example, improves personal fitness and also reduces air pollution.</p>
<p>Locally grown food is another simple example. It is usually fresher and more nutritious, and it can reduce carbon emissions because it does not travel long distances. Universities can use these everyday examples in English classes so that students practise grammar and vocabulary while also learning how communities can live more sustainably.</p>
<p>Nature-based activities, such as guided walks in a park or community gardening, also help. Time spent outdoors can improve concentration and make learning feel more meaningful. In this way, ecological intelligence is not only knowledge about the planet; it is a habit of making better daily choices.</p>
"""

LISTENING_SCRIPT = (
    "Good morning. Today we will talk about ecological intelligence. "
    "Ecological intelligence is the ability to understand how our actions affect the environment. "
    "Research shows that students learn better when lessons are connected to real, meaningful contexts. "
    "Walking or cycling instead of driving improves health and reduces air pollution. "
    "Locally grown food is fresher and also reduces carbon emissions. "
    "Nature-based activities such as guided nature walks help students remember information more easily."
)


def mcq(number, prompt, options, answer):
    return {
        "number": number,
        "qtype": "mcq",
        "prompt": prompt,
        "options": [{"value": letter, "label": f"{letter}) {text}"} for letter, text in options],
        "answer": answer,
    }


class Command(BaseCommand):
    help = "Clear all test materials and seed one reading, writing, listening, and speaking test."

    def handle(self, *args, **options):
        self.ensure_users()
        self.clear_materials()
        test = Test.objects.create(title="Practice Test 1", test_type="Thematic")
        self.seed_reading(test)
        self.seed_writing(test)
        self.seed_listening(test)
        self.seed_speaking(test)
        self.stdout.write(self.style.SUCCESS("Demo data is ready."))
        self.stdout.write("Student: 998901234567 / student123")
        self.stdout.write("Teacher: 998907654321 / teacher123")
        self.stdout.write("Admin:   admin / admin123  (also /admin/)")

    def ensure_users(self):
        users_spec = [
            {
                "username": "admin",
                "phone": "+998900000000",
                "first_name": "Super",
                "last_name": "Admin",
                "role": "Teacher",
                "password": "admin123",
                "is_staff": True,
                "is_superuser": True,
            },
            {
                "username": "998907654321",
                "phone": "+998907654321",
                "first_name": "Nodira",
                "last_name": "Teacher",
                "role": "Teacher",
                "password": "teacher123",
                "is_staff": False,
                "is_superuser": False,
            },
            {
                "username": "998901234567",
                "phone": "+998901234567",
                "first_name": "Aziz",
                "last_name": "Student",
                "role": "Student",
                "password": "student123",
                "is_staff": False,
                "is_superuser": False,
            },
        ]
        for spec in users_spec:
            password = spec.pop("password")
            user, _created = Users.objects.get_or_create(username=spec["username"], defaults=spec)
            for key, value in spec.items():
                setattr(user, key, value)
            user.set_password(password)
            user.save()
            spec["password"] = password
            self.stdout.write(f"User {user.username} / {password} ({user.role})")

    def clear_materials(self):
        SpeakingUserAnswer.objects.all().delete()
        WritingUserAnswer.objects.all().delete()
        ReadingUserAnswer.objects.all().delete()
        ListeningUserAnswer.objects.all().delete()
        SpeakingAnswer.objects.all().delete()
        WritingAnswer.objects.all().delete()
        ReadingAnswer.objects.all().delete()
        ListeningAnswer.objects.all().delete()
        Speaking.objects.all().delete()
        Writing.objects.all().delete()
        Reading.objects.all().delete()
        Listening.objects.all().delete()
        SpeakingMaterial.objects.all().delete()
        WritingMaterial.objects.all().delete()
        ReadingMaterial.objects.all().delete()
        ListeningMaterial.objects.all().delete()
        TestAccept.objects.all().delete()
        TestMaterial.objects.all().delete()
        Test.objects.all().delete()
        self.stdout.write("Removed existing tests and materials.")

    def seed_reading(self, test):
        tm = TestMaterial.objects.create(test=test, title="Reading Practice", is_view=True)
        rm = ReadingMaterial.objects.create(
            test_material=tm,
            title="Reading: Ecological intelligence",
            answer_time=2400,
        )
        items = [
            mcq(
                1,
                "What is ecological intelligence?",
                [
                    ("A", "Memorising the names of plants"),
                    ("B", "Understanding how everyday actions affect the environment"),
                    ("C", "Avoiding all technology"),
                    ("D", "Studying only in laboratories"),
                ],
                "B",
            ),
            mcq(
                2,
                "When do students remember information better?",
                [
                    ("A", "When lessons are connected to real life"),
                    ("B", "When they only memorise abstract facts"),
                    ("C", "When they never leave the classroom"),
                    ("D", "When they avoid environmental topics"),
                ],
                "A",
            ),
            mcq(
                3,
                "Walking or cycling instead of driving is said to:",
                [
                    ("A", "Increase air pollution"),
                    ("B", "Reduce personal fitness"),
                    ("C", "Improve fitness and reduce air pollution"),
                    ("D", "Have no effect on health"),
                ],
                "C",
            ),
            mcq(
                4,
                "Why is locally grown food described as useful?",
                [
                    ("A", "It always costs more"),
                    ("B", "It is usually fresher and can reduce carbon emissions"),
                    ("C", "It must travel long distances"),
                    ("D", "It cannot be used in English classes"),
                ],
                "B",
            ),
            mcq(
                5,
                "What can nature-based activities such as guided walks do?",
                [
                    ("A", "Make learning less meaningful"),
                    ("B", "Reduce concentration"),
                    ("C", "Replace all university courses"),
                    ("D", "Improve concentration and make learning more meaningful"),
                ],
                "D",
            ),
        ]
        reading = Reading(
            reading_material=rm,
            passage_number=1,
            title="Cities and ecological intelligence",
            content=READING_TEXT,
            questions="",
            description="Read the passage and answer the questions.",
        )
        reading.save()
        quiz_html = build_quiz_html(items)
        Reading.objects.filter(pk=reading.pk).update(
            questions=quiz_html,
            questions_raw=quiz_html,
            content=READING_TEXT,
            title="Cities and ecological intelligence",
        )
        for item in items:
            ReadingAnswer.objects.create(
                reading=reading,
                question_number=item["number"],
                true_answer=item["answer"],
            )
        self.stdout.write("Seeded 1 reading test with 5 questions.")

    def seed_writing(self, test):
        tm = TestMaterial.objects.create(test=test, title="Writing Practice", is_view=False)
        wm = WritingMaterial.objects.create(
            test_material=tm,
            title="Writing: Academic tasks",
            answer_time=3600,
        )
        task1 = Writing.objects.create(
            writing_material=wm,
            writing_task=1,
            description="Write at least 150 words.",
        )
        WritingAnswer.objects.create(
            writing=task1,
            question_number=1,
            question=(
                "<p>The chart below shows how people in a city travelled to work in 2010 and 2020.</p>"
                "<p>Summarise the information by selecting and reporting the main features, and make comparisons where relevant. "
                "You should write at least 150 words.</p>"
                "<ul><li>2010: car 60%, bus 25%, bicycle 10%, walking 5%</li>"
                "<li>2020: car 40%, bus 30%, bicycle 20%, walking 10%</li></ul>"
            ),
        )
        task2 = Writing.objects.create(
            writing_material=wm,
            writing_task=2,
            description="Write at least 250 words.",
        )
        WritingAnswer.objects.create(
            writing=task2,
            question_number=1,
            question=(
                "<p>Some people think that universities should teach students about environmental problems. "
                "Others believe that universities should focus only on academic subjects.</p>"
                "<p>Discuss both views and give your own opinion. You should write at least 250 words.</p>"
            ),
        )
        self.stdout.write("Seeded 1 writing test with Task 1 and Task 2.")

    def seed_listening(self, test):
        tm = TestMaterial.objects.create(test=test, title="Listening Practice", is_view=True)
        lm = ListeningMaterial.objects.create(
            test_material=tm,
            title="Listening: Ecological intelligence",
            answer_time=1800,
        )
        items = [
            mcq(
                1,
                "What is ecological intelligence?",
                [
                    ("A", "The ability to name every animal"),
                    ("B", "The ability to understand how our actions affect the environment"),
                    ("C", "The ability to drive faster"),
                    ("D", "The ability to avoid all food"),
                ],
                "B",
            ),
            mcq(
                2,
                "Students learn better when lessons are connected to:",
                [
                    ("A", "Abstract lists only"),
                    ("B", "Silent study only"),
                    ("C", "Real, meaningful contexts"),
                    ("D", "Long examinations only"),
                ],
                "C",
            ),
            mcq(
                3,
                "Walking or cycling instead of driving:",
                [
                    ("A", "Improves health and reduces air pollution"),
                    ("B", "Increases air pollution"),
                    ("C", "Has no health benefit"),
                    ("D", "Is not mentioned"),
                ],
                "A",
            ),
            mcq(
                4,
                "Locally grown food is described as:",
                [
                    ("A", "Less fresh"),
                    ("B", "More expensive only"),
                    ("C", "Fresher and able to reduce carbon emissions"),
                    ("D", "Impossible to find"),
                ],
                "C",
            ),
            mcq(
                5,
                "Guided nature walks help students:",
                [
                    ("A", "Forget information"),
                    ("B", "Remember information more easily"),
                    ("C", "Avoid outdoor activity"),
                    ("D", "Travel longer distances"),
                ],
                "B",
            ),
        ]
        quiz_html = build_quiz_html(items)
        section = Listening(
            listening_material=lm,
            listening_section=1,
            title="Part 1",
            questions=quiz_html,
            questions_raw=quiz_html,
            description="Listen and answer the questions.",
            audioscript=LISTENING_SCRIPT,
            is_script=True,
        )
        Listening.objects.bulk_create([section])
        section = Listening.objects.get(listening_material=lm, listening_section=1)
        audio_path = self.build_listening_audio()
        if audio_path:
            with open(audio_path, "rb") as fh:
                section.audio.save(audio_path.name, File(fh), save=False)
            Listening.objects.filter(pk=section.pk).update(audio=section.audio.name)
            TestMaterial.objects.filter(pk=tm.pk).update(audio=section.audio.name)
        for item in items:
            ListeningAnswer.objects.create(
                listening=section,
                question_number=item["number"],
                true_answer=item["answer"],
            )
        self.stdout.write("Seeded 1 listening test with 5 questions (transcript enabled).")

    def seed_speaking(self, test):
        tm = TestMaterial.objects.create(test=test, title="Speaking Practice", is_view=False)
        sm = SpeakingMaterial.objects.create(
            test_material=tm,
            title="Speaking: Daily life and the environment",
        )
        part1 = Speaking.objects.create(
            speaking_material=sm,
            speaking_part=1,
            prep_time=5,
            answer_time=45,
            comment="Short answers",
            description="Answer the questions.",
        )
        SpeakingAnswer.objects.create(
            speaking=part1,
            question_number=1,
            question="<p>Do you think the health of our planet and the health of our bodies are connected? Why?</p>",
        )
        SpeakingAnswer.objects.create(
            speaking=part1,
            question_number=2,
            question="<p>Describe one simple daily habit that can help the environment in your city.</p>",
        )
        self.stdout.write("Seeded 1 speaking test.")

    def build_listening_audio(self):
        media_dir = Path(settings.MEDIA_ROOT) / "listening_audios"
        media_dir.mkdir(parents=True, exist_ok=True)
        wav_path = media_dir / "ecological_intelligence.wav"
        aiff_path = media_dir / "ecological_intelligence.aiff"
        say = shutil.which("say")
        if say:
            try:
                subprocess.run(
                    [say, "-o", str(aiff_path), LISTENING_SCRIPT],
                    check=True,
                    capture_output=True,
                )
                afconvert = shutil.which("afconvert")
                if afconvert:
                    subprocess.run(
                        ["afconvert", "-f", "WAVE", "-d", "LEI16", str(aiff_path), str(wav_path)],
                        check=True,
                        capture_output=True,
                    )
                if wav_path.exists():
                    return wav_path
                if aiff_path.exists():
                    return aiff_path
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"Could not generate spoken audio: {exc}"))
        self.write_tone_wav(wav_path)
        return wav_path

    def write_tone_wav(self, path, seconds=4):
        framerate = 22050
        with wave.open(str(path), "w") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(framerate)
            for i in range(int(framerate * seconds)):
                value = int(7000 * math.sin(2 * math.pi * 440 * i / framerate))
                wav_file.writeframesraw(struct.pack("<h", value))
        self.stdout.write("Created a short audio file for listening.")
