
from django.contrib import admin
from django.urls import path,include
from django.conf import settings
from django.conf.urls.static import static
# from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework.routers import DefaultRouter
from rest_framework import permissions

schema_view = get_schema_view(
    openapi.Info(
        title="Wonders Education API",
        default_version="v1",
        description="API documentation for Wonders application",
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
    url="http://localhost:8000" 
    
)


router = DefaultRouter()


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('apps.urls')),
    path('ckeditor/', include('ckeditor_uploader.urls')),
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('', include('apps.web.urls')),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


