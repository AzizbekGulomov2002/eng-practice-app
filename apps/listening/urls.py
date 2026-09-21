from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ListeningViewSet,
    ListeningByMaterialView,
    ListeningAnswerView,
    ListeningUserAnswerListCreateView,
)

router = DefaultRouter()
router.register(r'listenings', ListeningViewSet, basename='listening')

urlpatterns = [
    path('', include(router.urls)),

    # Listening materialni olish
    path('listening/by-material/<int:pk>/', ListeningByMaterialView.as_view(), name='listening-by-material'),

    # Listening answer detail
    path('listening-answer/<int:id>/', ListeningAnswerView.as_view(), name='listening-answer-detail'),

    # User answers (GET - list, POST - create)
    path('listening-answers/<int:material_id>/', ListeningUserAnswerListCreateView.as_view(), name='listening-user-answer-list-create'),
]
