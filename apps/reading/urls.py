from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ReadingViewSet,
    ReadingByMaterialView,
    ReadingUserAnswerListCreateView
)

router = DefaultRouter()
router.register(r'readings', ReadingViewSet, basename='reading')

urlpatterns = [
    path('', include(router.urls)),
    path('reading/by-material/<int:pk>/', ReadingByMaterialView.as_view(), name='reading-by-material'),

    path("reading-answers/<int:material_id>/", ReadingUserAnswerListCreateView.as_view(), name="reading-answers"),

]