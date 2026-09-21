from django.urls import path, include
from apps.app.views import CustomAuthToken
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
# router.register(r'users', UserViewSet, basename='user')

urlpatterns = [
    path('', include(router.urls)),
    path('login/', CustomAuthToken.as_view(), name='api_token_auth'),
    path('', include('apps.reading.urls')),
    path('', include('apps.writing.urls')),
    path('', include('apps.listening.urls')),
    path('',include('apps.app.urls')),
    path('',include('apps.dashboard.urls')),
    path('', include('apps.speaking.urls')),

]