from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("sign-in/", views.sign_in, name="sign_in"),
    path("logout/", views.sign_out, name="logout"),
    path("tests/", views.test_list, name="test_list"),
    path("tests/<int:test_id>/", views.test_detail, name="test_detail"),
    path("start/<str:skill>/", views.start_skill, name="start_skill"),
    path("reading/<int:material_id>/", views.take_reading, name="take_reading"),
    path("writing/<int:material_id>/", views.take_writing, name="take_writing"),
    path("writing/<int:material_id>/part/<int:task_number>/", views.take_writing_task, name="take_writing_task"),
    path("speaking/<int:material_id>/", views.take_speaking, name="take_speaking"),
    path("listening/<int:material_id>/", views.take_listening, name="take_listening"),
    path("results/", views.my_results, name="my_results"),
    path("teacher/", views.teacher_home, name="teacher_home"),
    path("teacher/writing/<int:answer_id>/", views.evaluate_writing, name="evaluate_writing"),
    path("teacher/speaking/<int:answer_id>/", views.evaluate_speaking, name="evaluate_speaking"),
]
