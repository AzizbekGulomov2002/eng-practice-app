from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import WritingByMaterialView, WritingViewSet, WritingAnswersView

router = DefaultRouter()
router.register(r"writings", WritingViewSet, basename="writing")

urlpatterns = [
    path("", include(router.urls)), 
        
        
    path(
        "writing/by-material/<int:test_material_id>/",
        WritingByMaterialView.as_view(),
        name="writings-by-material"
    ),


    path(
        "writing-answers/<int:test_material_id>/",
        WritingAnswersView.as_view(),
        name="writing-answers"
    ),
]
