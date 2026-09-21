import html
import re
from bs4 import BeautifulSoup
from django.db.models import Q
from apps.app.models import Test, TestMaterial


def is_teacher(user):
    return bool(user and user.is_authenticated and (user.role == "Teacher" or user.is_superuser))


def is_student(user):
    return bool(user and user.is_authenticated and user.role == "Student")


def normalize_phone(value):
    return "".join(filter(str.isdigit, value or ""))


def tests_for_user(user):
    if not user or not user.is_authenticated:
        return Test.objects.none()
    return Test.objects.all().order_by("-date", "-id")


def materials_for_user_test(user, test):
    if not user or not user.is_authenticated:
        return TestMaterial.objects.none()
    return TestMaterial.objects.filter(test=test).prefetch_related(
        "reading_materials",
        "writing_materials",
        "speaking_materials",
        "listening_materials",
    )


def user_can_access_test_material(user, test_material):
    return bool(user and user.is_authenticated)


def user_can_access_reading_material(user, material):
    return user_can_access_test_material(user, material.test_material)


def user_can_access_writing_material(user, material):
    return user_can_access_test_material(user, material.test_material)


def user_can_access_speaking_material(user, material):
    return user_can_access_test_material(user, material.test_material)


def user_can_access_listening_material(user, material):
    return user_can_access_test_material(user, material.test_material)


SKILL_TAKE_URL = {
    "reading": "take_reading",
    "writing": "take_writing",
    "speaking": "take_speaking",
    "listening": "take_listening",
}


def skill_items_for_user(user, skill):
    skill = (skill or "").lower()
    items = []
    for test in tests_for_user(user):
        for tm in materials_for_user_test(user, test):
            for row in material_progress(user, tm):
                if row["kind"] == skill:
                    items.append({"test": test, "material": tm, **row})
    return items


def is_gradable_key(true_answer):
    key = (true_answer or "").strip().upper()
    return bool(key) and key not in {"OPINION", "OPEN", "-"}


def _numbered_items_from_html(html_text):
    soup = BeautifulSoup(html_text or "", "html.parser")
    found = {}
    for li in soup.select("ol li"):
        text = li.get_text(" ", strip=True)
        if not text:
            continue
        m = re.match(r"^(\d+)\.\s*(.+)$", text)
        if m:
            found[int(m.group(1))] = m.group(2).strip()
        elif found:
            nxt = max(found) + 1
            found[nxt] = text
        else:
            found[1] = text
    if found:
        return found
    for tag in soup.find_all(["p", "li", "div"]):
        text = tag.get_text(" ", strip=True)
        m = re.match(r"^(\d+)\.\s+(.+)$", text)
        if m:
            found[int(m.group(1))] = m.group(2).strip()
    return found


def parse_quiz_items(reading):
    """Build student-facing questions from ReadingAnswer rows + questions HTML."""
    soup = BeautifulSoup(reading.questions or "", "html.parser")
    numbered = _numbered_items_from_html(reading.questions)
    items = []
    answers = list(reading.answers.all().order_by("question_number"))
    if not answers and numbered:
        answers = [type("A", (), {"question_number": n, "true_answer": ""}) for n in sorted(numbered)]
    for answer in answers:
        number = answer.question_number
        el = soup.find(attrs={"data-number": str(number)})
        prompt = numbered.get(number) or f"Question {number}"
        qtype = "open"
        options = []
        if el:
            qtype = (el.get("data-type") or "open").strip().lower()
            prompt_el = el.find(class_="quiz-prompt")
            prompt = prompt_el.get_text(" ", strip=True) if prompt_el else el.get_text(" ", strip=True)
            for opt in el.select(".quiz-options [data-value], .quiz-options li"):
                value = opt.get("data-value") or ""
                label = opt.get_text(" ", strip=True)
                if not value and label:
                    value = label[:1].upper()
                if value:
                    options.append({"value": value, "label": label})
            if options and qtype == "open":
                qtype = "mcq"
        prompt = re.sub(r"^\d+\.\s*", "", prompt or "").strip()
        items.append(
            {
                "number": number,
                "prompt": prompt,
                "qtype": qtype,
                "options": options,
                "true_answer": answer.true_answer,
                "gradable": is_gradable_key(answer.true_answer),
            }
        )
    return items


def build_quiz_html(items):
    parts = ['<ol class="quiz-list">']
    for item in items:
        qtype = item.get("qtype") or "open"
        parts.append(
            f'<li class="quiz-item" data-number="{item["number"]}" data-type="{html.escape(qtype)}">'
        )
        parts.append(f'<p class="quiz-prompt">{item["prompt"]}</p>')
        if item.get("options"):
            parts.append('<ul class="quiz-options">')
            for opt in item["options"]:
                parts.append(
                    f'<li data-value="{html.escape(str(opt["value"]))}">{opt["label"]}</li>'
                )
            parts.append("</ul>")
        parts.append("</li>")
    parts.append("</ol>")
    return "".join(parts)


def qtype_label(qtype):
    mapping = {
        "mcq": "Quiz (MCQ)",
        "quiz": "Quiz (MCQ)",
        "closest": "Closest meaning",
        "open": "Open-ended",
        "openend": "Open-ended",
        "open-ended": "Open-ended",
    }
    return mapping.get((qtype or "").lower(), "Open-ended")


def _progress_item(kind, **kwargs):
    kwargs["kind"] = kind
    kwargs["image"] = f"images/{kind}.png"
    return kwargs


def material_progress(user, test_material):
    from apps.reading.models import ReadingAnswer, ReadingUserAnswer
    from apps.writing.models import Writing, WritingUserAnswer
    from apps.speaking.models import SpeakingAnswer, SpeakingUserAnswer

    data = []
    for rm in test_material.reading_materials.all():
        total = ReadingAnswer.objects.filter(reading__reading_material=rm).count()
        submitted = ReadingUserAnswer.objects.filter(
            user=user, reading__reading_material=rm
        ).count()
        correct = ReadingUserAnswer.objects.filter(
            user=user, reading__reading_material=rm, is_true=True
        ).count()
        data.append(
            _progress_item(
                "reading",
                id=rm.id,
                title=rm.title or "Reading",
                submitted=submitted > 0,
                total=total,
                correct=correct,
                pending_teacher=False,
            )
        )
    for wm in test_material.writing_materials.all():
        writings = Writing.objects.filter(writing_material=wm)
        submitted_qs = WritingUserAnswer.objects.filter(user=user, writing__writing_material=wm)
        unevaluated = submitted_qs.filter(Q(score__isnull=True)).exists()
        data.append(
            _progress_item(
                "writing",
                id=wm.id,
                title=wm.title or "Writing",
                submitted=submitted_qs.exists(),
                total=writings.count(),
                correct=submitted_qs.exclude(score__isnull=True).count(),
                pending_teacher=submitted_qs.exists() and unevaluated,
            )
        )
    for sm in test_material.speaking_materials.all():
        total = SpeakingAnswer.objects.filter(speaking__speaking_material=sm).count()
        submitted_qs = SpeakingUserAnswer.objects.filter(user=user, speaking=sm)
        unevaluated = submitted_qs.filter(Q(score__isnull=True)).exists()
        data.append(
            _progress_item(
                "speaking",
                id=sm.id,
                title=sm.title or "Speaking",
                submitted=submitted_qs.exists(),
                total=total,
                correct=submitted_qs.exclude(score__isnull=True).count(),
                pending_teacher=submitted_qs.exists() and unevaluated,
            )
        )
    from apps.listening.models import ListeningAnswer, ListeningUserAnswer

    for lm in test_material.listening_materials.all():
        total = ListeningAnswer.objects.filter(listening__listening_material=lm).count()
        submitted_qs = ListeningUserAnswer.objects.filter(
            user=user, listening__listening_material=lm
        )
        correct = submitted_qs.filter(is_true=True).count()
        data.append(
            _progress_item(
                "listening",
                id=lm.id,
                title=lm.title or "Listening",
                submitted=submitted_qs.exists(),
                total=total,
                correct=correct,
                pending_teacher=False,
            )
        )
    return data
