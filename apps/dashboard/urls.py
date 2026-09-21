from django.urls import path
from apps.dashboard.views import (
    ResultsAPIView,
    ResultsByTypeAPIView,
    TeacherDashboardView,
    GroupDetailView,
    StudentDetailView,
    StudentTestResultsByTypeView,
    StudentListView,
    AllTeacherDashboardView,
    ThematicResultsByTypeAPIView,
    detail_material,
    my_mock_test_details,
    my_mock_tests,
    my_thematic_test_details,
    my_thematic_tests,
    student_mock_statistics,
    student_test_detailed_results,
    student_thematic_statistics,
    thematic_material_info,
    thematic_statistics, thematic_material_info_by_type, thematic_statistics_by_type, ThematicStatisticsAPIView,
    dashboard_statistics, student_skill_detailed_results, ThematicAllResultsAPIView, AllResultsByTypeAPIView
)

from apps.dashboard.views import test_info,student_results_by_type_and_skill,student_results_by_type_and_skill_detail,statistics

urlpatterns = [
    path('teacher/groups/', TeacherDashboardView.as_view(), name='teacher-dashboard'),
    path('teacher/all_groups/', AllTeacherDashboardView.as_view(), name='teacher-dashboard'),
    path('teacher/students/', StudentListView.as_view(), name='student-list'),
    path('teacher/groups/<int:group_id>/', GroupDetailView.as_view(), name='group-detail'),
    path('teacher/students/<int:student_id>/', StudentDetailView.as_view(), name='student-detail'),
    
    path('teacher/students/<int:student_id>/<str:test_type>/', 
         StudentTestResultsByTypeView.as_view(), name='student-test-results'),
    
    path('mock/statistics/', statistics, name='mock_statistics'),
    path('student-mocks/<int:student_id>/', student_mock_statistics, name='student_mock_statistics'),
    path('student-mocks/<int:student_id>/<int:material_id>/', student_test_detailed_results, name='student_test_detailed_results'),

    
    path('student-thematics/<int:student_id>/', student_thematic_statistics, name='student_thematic_statistics'),
    path('student-thematics/<int:student_id>/reading/<int:skill_id>/', student_skill_detailed_results, {'skill_type': 'reading'}, name='student_reading_results'),
    path('student-thematics/<int:student_id>/listening/<int:skill_id>/', student_skill_detailed_results, {'skill_type': 'listening'}, name='student_listening_results'),
    path('student-thematics/<int:student_id>/writing/<int:skill_id>/', student_skill_detailed_results, {'skill_type': 'writing'}, name='student_writing_results'),
    path('student-thematics/<int:student_id>/speaking/<int:skill_id>/', student_skill_detailed_results, {'skill_type': 'speaking'}, name='student_speaking_results'),

    
    path('me/thematics/', my_thematic_tests, name='my_thematic_tests'),
    path('me/thematics/<int:material_id>/', my_thematic_test_details, name='my_thematic_test_details'),
    path('me/mocks/', my_mock_tests, name='my_mock_tests'),
    path('me/mocks/<int:material_id>/', my_mock_test_details, name='my_mock_test_details'),

    path('thematic/statistics/', thematic_statistics, name='thematic_statistics'),

    # New class-based view endpoints
    path('thematic/statistics/<str:material_type>/', ThematicStatisticsAPIView.as_view(),
         name='thematic_statistics_by_type'),

    path("mock-material-info/<int:pk>/", test_info, name="test-info"),
    path("thematic-material-info/<int:pk>/", thematic_material_info, name="thematic-material-info"),

    # New filtered patterns
    path("thematic-material-info/reading/<int:pk>/", thematic_material_info_by_type, {'material_type': 'reading'},
         name="thematic-material-info-reading"),
    path("thematic-material-info/listening/<int:pk>/", thematic_material_info_by_type, {'material_type': 'listening'},
         name="thematic-material-info-listening"),
    path("thematic-material-info/writing/<int:pk>/", thematic_material_info_by_type, {'material_type': 'writing'},
         name="thematic-material-info-writing"),
    path("thematic-material-info/speaking/<int:pk>/", thematic_material_info_by_type, {'material_type': 'speaking'},
         name="thematic-material-info-speaking"),

    path('detail-material/reading/<int:skill_material_id>/', detail_material, {'skill_type': 'reading'},
         name='detail_material_reading'),
    path('detail-material/listening/<int:skill_material_id>/', detail_material, {'skill_type': 'listening'},
         name='detail_material_listening'),
    path('detail-material/writing/<int:skill_material_id>/', detail_material, {'skill_type': 'writing'},
         name='detail_material_writing'),
    path('detail-material/speaking/<int:skill_material_id>/', detail_material, {'skill_type': 'speaking'},
         name='detail_material_speaking'),

    path('results/', ResultsAPIView.as_view(), name='results'),
    path('results/<str:result_type>/', ResultsByTypeAPIView.as_view(), name='results-by-type'),
    path('all-results/<str:result_type>/', AllResultsByTypeAPIView.as_view(), name='results-by-type'),

    path('results/thematic/<str:result_type>/', ThematicResultsByTypeAPIView.as_view(), name='thematic-results-by-type'),
    path('all-results/thematic/<str:result_type>/', ThematicAllResultsAPIView.as_view(), name='thematic-results-by-type'),


    
    path(
        "student/detail/<int:pk>/<str:test_type>/<str:skill>/",
        student_results_by_type_and_skill,
        name="student-results-by-skill"
    ),
    
    path(
        "student/info/<int:pk>/<str:test_type>/<str:skill>/<int:obj_id>/",
        student_results_by_type_and_skill_detail,
        name="student-results-by-skill-detail"
    ),

    path('dashboard-statistics/', dashboard_statistics, name='statistics'),


]