from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    SpeakingsViewSet,
    SpeakingAnswerListView,
    SpeakingUserAnswerCreateView,
    SpeakingByMaterialView
)
router = DefaultRouter()
router.register(r'speakings', SpeakingsViewSet, basename='speaking-section')

urlpatterns = [
    path(
        'speaking/by-material/<int:test_material_id>/',
            SpeakingByMaterialView.as_view(), 
            name='speaking-by-material'
    ),
    path(
        "speaking/<int:speaking_id>/answers/",
        SpeakingAnswerListView.as_view(),
        name="speaking-answers",
    ),

   path("speaking-answers/", SpeakingUserAnswerCreateView.as_view(), name="speaking-answer-create"),
]
urlpatterns += router.urls
