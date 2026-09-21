from django.urls import path

from .views import (
    MeAPIView, TestMaterialistListView,TestListView
)
urlpatterns = [
    path("tests/", TestListView.as_view(), name="tests"),
    path("test-materials/", TestMaterialistListView.as_view(), name="test-materials"),
    path('me/', MeAPIView.as_view(), name='me'),
]
