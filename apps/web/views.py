from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import strip_tags
from django.views.decorators.http import require_http_methods

from apps.app.models import Test, Users
from apps.listening.models import Listening, ListeningAnswer, ListeningMaterial, ListeningUserAnswer
from apps.reading.models import Reading, ReadingAnswer, ReadingMaterial, ReadingUserAnswer
from apps.speaking.models import Speaking, SpeakingAnswer, SpeakingMaterial, SpeakingUserAnswer
from apps.writing.models import Writing, WritingAnswer, WritingMaterial, WritingUserAnswer
from apps.web.utils import (
    SKILL_TAKE_URL,
    is_teacher,
    material_progress,
    materials_for_user_test,
    normalize_phone,
    parse_quiz_items,
    qtype_label,
    skill_items_for_user,
    tests_for_user,
    user_can_access_listening_material,
    user_can_access_reading_material,
    user_can_access_speaking_material,
    user_can_access_test_material,
    user_can_access_writing_material,
)


def home(request):
    return render(request, "web/home.html")


def about(request):
    return render(request, "web/about.html")


def _details_key(skill, material_id):
    return f"details_ok_{skill}_{material_id}"


def _candidate_name(user):
    return f"{user.first_name} {user.last_name}".strip() or user.username


def submitted_home():
    return redirect(f"{reverse('test_list')}?submitted=1")


def _writing_time_label(seconds):
    seconds = int(seconds or 0)
    minutes = max(1, seconds // 60) if seconds else 1
    hours = minutes // 60
    if hours and minutes % 60 == 0:
        return "1 hour" if hours == 1 else f"{hours} hours"
    return "1 minute" if minutes == 1 else f"{minutes} minutes"


def _writing_parts(writings, submitted_ids):
    parts = []
    for writing in writings:
        answers = list(writing.writing_answers.all().order_by("question_number"))
        preview = (writing.description or "").strip()
        if not preview and answers:
            preview = strip_tags(answers[0].question or "").strip()
        parts.append(
            {
                "writing": writing,
                "submitted": writing.id in submitted_ids,
                "preview": preview,
            }
        )
    return parts


def _writing_timer_context(request, material, already):
    return {
        "timer_seconds": 0 if already else (material.answer_time or 3600),
        "timer_key": f"writing-timer-{request.user.id}-{material.id}",
    }


def maybe_confirm_details(request, skill, material_id, resume_url):
    key = _details_key(skill, material_id)
    if request.method == "POST" and request.POST.get("confirm_details"):
        request.session[key] = True
        return redirect(resume_url)
    if request.method == "GET" and not request.session.get(key):
        return render(
            request,
            "web/confirm_details.html",
            {
                "full_name": f"{request.user.first_name} {request.user.last_name}".strip()
                or request.user.username,
                "phone": request.user.phone or request.user.username,
                "resume_url": resume_url,
            },
        )
    return None


@require_http_methods(["GET", "POST"])
def sign_in(request):
    if request.user.is_authenticated:
        return redirect("test_list")
    if request.method == "POST":
        phone = (request.POST.get("phone") or "").strip()
        password = request.POST.get("password") or ""
        digits = normalize_phone(phone)
        user = None
        for candidate in (digits, phone):
            if not candidate:
                continue
            user = authenticate(request, username=candidate, password=password)
            if user:
                break
        if user is None and phone:
            found = Users.objects.filter(
                Q(username=phone) | Q(username=digits) | Q(phone=phone) | Q(phone=digits)
            ).first()
            if found:
                user = authenticate(request, username=found.username, password=password)
        if user is None:
            messages.error(request, "Username, phone number or password is incorrect.")
        elif not user.is_active:
            messages.error(request, "This account is inactive.")
        else:
            login(request, user)
            next_url = request.GET.get("next") or request.POST.get("next")
            return redirect(next_url or "test_list")
    return render(request, "web/sign_in.html")


def sign_out(request):
    logout(request)
    return redirect("home")


@login_required
def test_list(request):
    return render(request, "web/test_list.html")


@login_required
def test_detail(request, test_id):
    test = get_object_or_404(Test, pk=test_id)
    materials = materials_for_user_test(request.user, test)
    if not materials.exists() and not is_teacher(request.user):
        messages.error(request, "You do not have access to this test.")
        return redirect("test_list")
    sections = []
    for tm in materials:
        sections.append(
            {
                "material": tm,
                "progress": material_progress(request.user, tm),
            }
        )
    return render(
        request,
        "web/test_detail.html",
        {"test": test, "sections": sections},
    )


@login_required
def start_skill(request, skill):
    skill = (skill or "").lower()
    take_url = SKILL_TAKE_URL.get(skill)
    if not take_url:
        messages.error(request, "Unknown skill.")
        return redirect("home")
    items = skill_items_for_user(request.user, skill)
    if len(items) == 1:
        return redirect(take_url, items[0]["id"])
    back_test_id = items[0]["test"].id if items else None
    return render(
        request,
        "web/skill_list.html",
        {
            "skill": skill,
            "skill_title": skill.title(),
            "skill_image": f"images/{skill}.png",
            "items": items,
            "take_url": take_url,
            "back_test_id": back_test_id,
        },
    )


@login_required
def take_reading(request, material_id):
    material = get_object_or_404(
        ReadingMaterial.objects.select_related("test_material__test"),
        pk=material_id,
    )
    if not user_can_access_reading_material(request.user, material):
        messages.error(request, "You do not have access to this reading test.")
        return redirect("test_list")

    passages = list(
        Reading.objects.filter(reading_material=material)
        .prefetch_related("answers")
        .order_by("passage_number", "id")
    )
    submitted_qs = ReadingUserAnswer.objects.filter(
        user=request.user, reading__reading_material=material
    )
    already = submitted_qs.exists()
    if not already:
        gated = maybe_confirm_details(
            request,
            "reading",
            material.id,
            reverse("take_reading", args=[material.id]),
        )
        if gated:
            return gated

    if request.method == "POST" and not already:
        with transaction.atomic():
            for passage in passages:
                for answer in passage.answers.all():
                    field = f"q_{passage.id}_{answer.question_number}"
                    value = (request.POST.get(field) or "").strip()
                    ReadingUserAnswer.objects.create(
                        user=request.user,
                        reading=passage,
                        question_number=answer.question_number,
                        answer=value,
                    )
        return redirect("take_reading", material_id=material.id)

    given = {
        (row.reading_id, row.question_number): row
        for row in submitted_qs
    }
    question_blocks = []
    total = 0
    correct = 0
    for passage in passages:
        items = parse_quiz_items(passage)
        for item in items:
            row = given.get((passage.id, item["number"]))
            item["given"] = row.answer if row else ""
            item["is_true"] = bool(row and row.is_true)
            item["qtype_label"] = qtype_label(item["qtype"])
            if item.get("gradable"):
                total += 1
                if row and row.is_true:
                    correct += 1
        question_blocks.append(
            {
                "obj_id": passage.id,
                "title": passage.title or passage.get_passage_number_display(),
                "items": items,
            }
        )

    return render(
        request,
        "web/take_reading.html",
        {
            "material": material,
            "passages": passages,
            "question_blocks": question_blocks,
            "already": already,
            "show_answers": already,
            "total": total,
            "correct": correct,
            "readonly": already,
            "candidate_name": _candidate_name(request.user),
        },
    )


@login_required
def take_writing(request, material_id):
    material = get_object_or_404(
        WritingMaterial.objects.select_related("test_material__test"),
        pk=material_id,
    )
    if not user_can_access_writing_material(request.user, material):
        messages.error(request, "You do not have access to this writing test.")
        return redirect("test_list")
    writings = list(
        Writing.objects.filter(writing_material=material)
        .prefetch_related("writing_answers")
        .order_by("writing_task", "id")
    )
    if not writings:
        messages.error(request, "This writing test has no tasks yet.")
        return redirect("test_list")
    submitted_ids = set(
        WritingUserAnswer.objects.filter(
            user=request.user, writing__writing_material=material
        ).values_list("writing_id", flat=True)
    )
    already = len(submitted_ids) == len(writings)
    if not already:
        gated = maybe_confirm_details(
            request,
            "writing",
            material.id,
            reverse("take_writing", args=[material.id]),
        )
        if gated:
            return gated
        intro_key = f"writing_intro_{material.id}"
        if request.method == "POST" and request.POST.get("start_writing"):
            request.session[intro_key] = True
            return redirect("take_writing", material_id=material.id)
        if not request.session.get(intro_key):
            return render(
                request,
                "web/writing_intro.html",
                {
                    "material": material,
                    "time_label": _writing_time_label(material.answer_time or 3600),
                    "part_count": len(writings),
                },
            )
        if request.method == "POST" and (
            request.POST.get("writing_timeout") or request.POST.get("timed_out")
        ):
            with transaction.atomic():
                for writing in writings:
                    if writing.id in submitted_ids:
                        continue
                    WritingUserAnswer.objects.get_or_create(
                        user=request.user,
                        writing=writing,
                        defaults={
                            "question_number": 1,
                            "answer": "(Time ended. No answer submitted.)",
                        },
                    )
            return submitted_home()

    return render(
        request,
        "web/writing_parts.html",
        {
            "material": material,
            "parts": _writing_parts(writings, submitted_ids),
            "already": already,
            "candidate_name": _candidate_name(request.user),
            **_writing_timer_context(request, material, already),
        },
    )


@login_required
def take_writing_task(request, material_id, writing_id):
    material = get_object_or_404(
        WritingMaterial.objects.select_related("test_material__test"),
        pk=material_id,
    )
    if not user_can_access_writing_material(request.user, material):
        messages.error(request, "You do not have access to this writing test.")
        return redirect("test_list")

    writings = list(
        Writing.objects.filter(writing_material=material)
        .prefetch_related("writing_answers")
        .order_by("writing_task", "id")
    )
    writing = next((row for row in writings if row.id == writing_id), None)
    if writing is None:
        writing = next((row for row in writings if row.writing_task == writing_id), None)
    if writing is None:
        messages.error(request, "That writing part was not found.")
        return redirect("take_writing", material_id=material.id)

    existing = WritingUserAnswer.objects.filter(
        user=request.user, writing=writing
    ).first()
    submitted_ids = set(
        WritingUserAnswer.objects.filter(
            user=request.user, writing__writing_material=material
        ).values_list("writing_id", flat=True)
    )
    all_submitted = len(submitted_ids) >= len(writings)
    if not all_submitted:
        if not request.session.get(_details_key("writing", material.id)) or not request.session.get(
            f"writing_intro_{material.id}"
        ):
            return redirect("take_writing", material_id=material.id)

    readonly = bool(existing)
    index = next((i for i, row in enumerate(writings) if row.id == writing.id), 0)
    prev_writing = writings[index - 1] if index > 0 else None
    next_writing = writings[index + 1] if index + 1 < len(writings) else None

    if request.method == "POST" and not existing:
        text = (request.POST.get(f"writing_{writing.id}") or "").strip()
        timed_out = request.POST.get("timed_out") == "1"
        if not text and timed_out:
            text = "(Time ended. No answer submitted.)"
        if not text:
            messages.error(request, "Please write your answer before submitting.")
            return redirect(
                "take_writing_task",
                material_id=material.id,
                writing_id=writing.id,
            )
        with transaction.atomic():
            WritingUserAnswer.objects.create(
                user=request.user,
                writing=writing,
                question_number=1,
                answer=text,
            )
            if timed_out:
                for other in writings:
                    if other.id == writing.id:
                        continue
                    WritingUserAnswer.objects.get_or_create(
                        user=request.user,
                        writing=other,
                        defaults={
                            "question_number": 1,
                            "answer": "(Time ended. No answer submitted.)",
                        },
                    )
                return submitted_home()
        remaining = [row for row in writings if row.id not in submitted_ids and row.id != writing.id]
        if remaining:
            return redirect("take_writing", material_id=material.id)
        return submitted_home()

    return render(
        request,
        "web/take_writing.html",
        {
            "material": material,
            "writing": writing,
            "questions": writing.writing_answers.all().order_by("question_number"),
            "answer": existing,
            "already": readonly,
            "readonly": readonly,
            "prev_writing": prev_writing,
            "next_writing": next_writing,
            "parts": writings,
            "candidate_name": _candidate_name(request.user),
            **_writing_timer_context(request, material, all_submitted),
        },
    )


@login_required
def take_speaking(request, material_id):
    material = get_object_or_404(
        SpeakingMaterial.objects.select_related("test_material__test"),
        pk=material_id,
    )
    if not user_can_access_speaking_material(request.user, material):
        messages.error(request, "You do not have access to this speaking test.")
        return redirect("test_list")

    sections = list(
        Speaking.objects.filter(speaking_material=material)
        .prefetch_related("speaking_answer")
        .order_by("speaking_part", "id")
    )
    existing = {
        row.question_number: row
        for row in SpeakingUserAnswer.objects.filter(user=request.user, speaking=material)
    }
    already = bool(existing)
    questions = []
    for section in sections:
        for q in section.speaking_answer.all().order_by("question_number"):
            questions.append({"section": section, "question": q, "answer": existing.get(q.question_number)})

    if not already:
        gated = maybe_confirm_details(
            request,
            "speaking",
            material.id,
            reverse("take_speaking", args=[material.id]),
        )
        if gated:
            return gated
        intro_key = f"speaking_intro_{material.id}"
        if request.method == "POST" and request.POST.get("start_speaking"):
            request.session[intro_key] = True
            return redirect("take_speaking", material_id=material.id)
        if not request.session.get(intro_key):
            total = sum(
                (item["section"].prep_time or 0) + (item["section"].answer_time or 0)
                for item in questions
            )
            minutes = max(1, (total + 59) // 60)
            return render(
                request,
                "web/speaking_intro.html",
                {
                    "material": material,
                    "time_label": f"{minutes} minutes" if minutes != 1 else "1 minute",
                    "part_count": len(sections),
                },
            )

    if request.method == "POST" and not already:
        uploads = {}
        for item in questions:
            qn = item["question"].question_number
            upload = request.FILES.get(f"record_{qn}")
            if upload:
                uploads[qn] = upload
        if not uploads:
            messages.error(request, "Please record an answer before submitting.")
            return redirect("take_speaking", material_id=material.id)
        with transaction.atomic():
            for qn, upload in uploads.items():
                SpeakingUserAnswer.objects.create(
                    user=request.user,
                    speaking=material,
                    question_number=qn,
                    record=upload,
                )
        return submitted_home()

    payload = [
        {
            "number": item["question"].question_number,
            "part": item["section"].speaking_part,
            "text": strip_tags(item["question"].question or "").strip(),
            "html": item["question"].question or "",
            "prep_time": item["section"].prep_time or 5,
            "answer_time": item["section"].answer_time or 20,
        }
        for item in questions
    ]
    return render(
        request,
        "web/take_speaking.html",
        {
            "material": material,
            "questions": questions,
            "questions_json": payload,
            "already": already,
            "readonly": already,
            "candidate_name": _candidate_name(request.user),
        },
    )


@login_required
def take_listening(request, material_id):
    material = get_object_or_404(
        ListeningMaterial.objects.select_related("test_material__test"),
        pk=material_id,
    )
    if not user_can_access_listening_material(request.user, material):
        messages.error(request, "You do not have access to this listening test.")
        return redirect("test_list")

    sections = list(
        Listening.objects.filter(listening_material=material)
        .prefetch_related("answers")
        .order_by("listening_section", "id")
    )
    submitted_qs = ListeningUserAnswer.objects.filter(
        user=request.user, listening__listening_material=material
    )
    already = submitted_qs.exists()
    if not already:
        gated = maybe_confirm_details(
            request,
            "listening",
            material.id,
            reverse("take_listening", args=[material.id]),
        )
        if gated:
            return gated

    if request.method == "POST" and not already:
        with transaction.atomic():
            for section in sections:
                for answer in section.answers.all():
                    field = f"q_{section.id}_{answer.question_number}"
                    value = (request.POST.get(field) or "").strip()
                    ListeningUserAnswer.objects.create(
                        user=request.user,
                        listening=section,
                        question_number=answer.question_number,
                        answer=value,
                    )
        return redirect("take_listening", material_id=material.id)

    given = {
        (row.listening_id, row.question_number): row
        for row in submitted_qs
    }
    question_blocks = []
    total = 0
    correct = 0
    for section in sections:
        items = parse_quiz_items(section)
        for item in items:
            row = given.get((section.id, item["number"]))
            item["given"] = row.answer if row else ""
            item["is_true"] = bool(row and row.is_true)
            item["qtype_label"] = qtype_label(item["qtype"])
            if item.get("gradable"):
                total += 1
                if row and row.is_true:
                    correct += 1
        question_blocks.append(
            {
                "obj_id": section.id,
                "title": section.title or section.get_listening_section_display(),
                "items": items,
            }
        )

    return render(
        request,
        "web/take_listening.html",
        {
            "material": material,
            "sections": sections,
            "question_blocks": question_blocks,
            "already": already,
            "show_answers": already,
            "total": total,
            "correct": correct,
            "readonly": already,
            "has_audio": any(bool(section.audio) for section in sections),
            "show_script": any(section.is_script and section.audioscript for section in sections),
            "candidate_name": _candidate_name(request.user),
        },
    )


@login_required
def my_results(request):
    reading_rows = []
    for material in ReadingMaterial.objects.select_related("test_material__test"):
        if not user_can_access_reading_material(request.user, material):
            continue
        answers = ReadingUserAnswer.objects.filter(
            user=request.user, reading__reading_material=material
        )
        if not answers.exists():
            continue
        total = ReadingAnswer.objects.filter(reading__reading_material=material).count()
        correct = answers.filter(is_true=True).count()
        reading_rows.append({"material": material, "total": total, "correct": correct})

    writing_rows = WritingUserAnswer.objects.filter(user=request.user).select_related(
        "writing__writing_material__test_material__test"
    )
    speaking_rows = SpeakingUserAnswer.objects.filter(user=request.user).select_related(
        "speaking__test_material__test"
    )
    listening_rows = []
    for material in ListeningMaterial.objects.select_related("test_material__test"):
        if not user_can_access_listening_material(request.user, material):
            continue
        answers = ListeningUserAnswer.objects.filter(
            user=request.user, listening__listening_material=material
        )
        if not answers.exists():
            continue
        total = ListeningAnswer.objects.filter(listening__listening_material=material).count()
        correct = answers.filter(is_true=True).count()
        listening_rows.append({"material": material, "total": total, "correct": correct})
    return render(
        request,
        "web/results.html",
        {
            "reading_rows": reading_rows,
            "writing_rows": writing_rows,
            "speaking_rows": speaking_rows,
            "listening_rows": listening_rows,
        },
    )


def teacher_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not is_teacher(request.user):
            messages.error(request, "Only teachers can open this page.")
            return redirect("test_list")
        return view_func(request, *args, **kwargs)

    return wrapper


@teacher_required
def teacher_home(request):
    writing_pending = (
        WritingUserAnswer.objects.filter(score__isnull=True)
        .select_related("user", "writing__writing_material")
        .order_by("created_at")
    )
    writing_done = (
        WritingUserAnswer.objects.exclude(score__isnull=True)
        .select_related("user", "writing__writing_material")
        .order_by("-created_at")[:30]
    )
    speaking_pending = (
        SpeakingUserAnswer.objects.filter(score__isnull=True)
        .select_related("user", "speaking")
        .order_by("created_at")
    )
    speaking_done = (
        SpeakingUserAnswer.objects.exclude(score__isnull=True)
        .select_related("user", "speaking")
        .order_by("-created_at")[:30]
    )
    return render(
        request,
        "web/teacher_home.html",
        {
            "writing_pending": writing_pending,
            "writing_done": writing_done,
            "speaking_pending": speaking_pending,
            "speaking_done": speaking_done,
        },
    )


@teacher_required
def evaluate_writing(request, answer_id):
    answer = get_object_or_404(
        WritingUserAnswer.objects.select_related("user", "writing__writing_material"),
        pk=answer_id,
    )
    questions = WritingAnswer.objects.filter(writing=answer.writing).order_by("question_number")
    if request.method == "POST":
        score_raw = request.POST.get("score")
        feedback = request.POST.get("feedback") or ""
        try:
            score = float(score_raw)
        except (TypeError, ValueError):
            messages.error(request, "Enter a valid score.")
            return redirect("evaluate_writing", answer_id=answer.id)
        if score < 0 or score > 9:
            messages.error(request, "Score must be between 0 and 9.")
            return redirect("evaluate_writing", answer_id=answer.id)
        answer.score = score
        answer.feedback = feedback
        answer.save()
        messages.success(request, "Writing evaluation saved.")
        return redirect("teacher_home")
    return render(
        request,
        "web/evaluate_writing.html",
        {"answer": answer, "questions": questions},
    )


@teacher_required
def evaluate_speaking(request, answer_id):
    answer = get_object_or_404(
        SpeakingUserAnswer.objects.select_related("user", "speaking"),
        pk=answer_id,
    )
    question = SpeakingAnswer.objects.filter(
        speaking__speaking_material=answer.speaking,
        question_number=answer.question_number,
    ).first()
    if request.method == "POST":
        score_raw = request.POST.get("score")
        feedback = request.POST.get("feedback") or ""
        try:
            score = float(score_raw)
        except (TypeError, ValueError):
            messages.error(request, "Enter a valid score.")
            return redirect("evaluate_speaking", answer_id=answer.id)
        if score < 0 or score > 9:
            messages.error(request, "Score must be between 0 and 9.")
            return redirect("evaluate_speaking", answer_id=answer.id)
        answer.score = score
        answer.feedback = feedback
        answer.save()
        messages.success(request, "Speaking evaluation saved.")
        return redirect("teacher_home")
    return render(
        request,
        "web/evaluate_speaking.html",
        {"answer": answer, "question": question},
    )
