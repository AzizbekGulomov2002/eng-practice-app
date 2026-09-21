import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# .env ni yuklaymiz
load_dotenv(BASE_DIR / ".env")

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-do=@*#%y8t-5xnl#-cz+pfach)!hkg_l_rvcz_&=vk0&0t#w@('

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True
APPEND_SLASH = True
ALLOWED_HOSTS = ["*"]


# Application definition

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    'config',  # For management commands
    'apps.reading',
    'apps.app',
    'apps.writing',
    'apps.listening',
    'apps.speaking',
    'apps.dashboard',
    'apps.web',
    
    'ckeditor',
    'ckeditor_uploader',
    
    'rest_framework',
    'rest_framework.authtoken',
    "corsheaders",
    # 'drf_spectacular',
    'drf_yasg',
    "django_filters",
]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:8000",   
    "http://127.0.0.1:8000",
    "http://localhost:3000",  
    "http://127.0.0.1:3000",
    "http://localhost:5173",  
    "http://localhost:5174",  
    "https://cd-ielts-one.vercel.app",
    "https://ieltswonder.uz",
    "https://admin.ieltswonder.uz",
    "https://cdmock.pythonanywhere.com",
    "https://46e42f3dd7ab.ngrok-free.app"
]

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5173",   
    "http://localhost:5174",   
    "https://ieltswonder.uz",
    "https://admin.ieltswonder.uz",
    "https://cdmock.pythonanywhere.com",
    "https://46e42f3dd7ab.ngrok-free.app"
]


CORS_ALLOW_CREDENTIALS = True


SWAGGER_SETTINGS = {
    "SECURITY_DEFINITIONS": {
        "Token": {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": "Token-based authentication. Example: **Token 123456789abcdef**"
        }
    }
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'apps.app.views': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}


REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ),
    
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    "apps.app.middleware.DeviceUUIDMiddleware",  
    "apps.app.middleware.StudentActionLoggingMiddleware",  
]




ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


CKEDITOR_UPLOAD_PATH = "uploads/" 
CKEDITOR_CONFIGS = {
    'default': {
        'toolbar': 'full',
        'height': 300,
        'width': '100%',
    },
}

JAZZMIN_SETTINGS = {
    # Branding
    "site_title":    "EcoCourse",
    "site_header":   "EcoCourse",
    "site_brand":    "EcoCourse",
    "welcome_sign":  "Welcome to the EcoCourse admin panel",
    "copyright":     "EcoCourse",
    "custom_css":    "css/admin_brand.css",

    # Search & UI
    "search_model": ["app.Users"],
    "show_sidebar": True,
    "related_modal_active": False,
    "hide_models": [
        "app.StudentGroup",
        "app.TestAccept",
        "app.AllowedIP",
    ],
    
    "order_with_respect_to": [
        "app",       
        "reading",
        "listening",
        "writing",
        "speaking",
        "auth",       
    ],

    "icons": {
        "app.Users":"fas fa-user",
        "app.TestMaterial":"fas fa-book-open",
        "app.Test":"fas fa-file-signature",

        
        # Reading
        "reading.Reading": "fas fa-file-alt",
        "reading.ReadingQuestion": "fas fa-question-circle",
        "reading.ReadingAnswer": "fas fa-pencil-alt",
        "reading.ReadingMaterial": "fas fa-book-reader",
        "reading.ReadingUserAnswer": "fas fa-user-edit",

        
        # Listening
        "listening.Listening": "fas fa-headphones",
        "listening.ListeningQuestion": "fas fa-question",
        "listening.ListeningAnswer": "fas fa-microphone",
        "listening.ListeningMaterial": "fas fa-volume-up",
        "listening.ListeningUserAnswer": "fas fa-user-check",
    
        # Writing
        "writing.Writing": "fas fa-pen-fancy",
        "writing.WritingAnswer": "fas fa-comment-dots",
        "writing.WritingMaterial": "fas fa-file-word",
        "writing.WritingUserAnswer": "fas fa-user-pen",

        # Speaking
        "speaking.SpeakingMaterial": "fas fa-comments",
        "speaking.SpeakingAnswer": "fas fa-microphone-alt",
        "speaking.Speaking":             "fas fa-comments",
        "speaking.SpeakingUserAnswer":       "fas fa-video",
    },

    # Defaults
    "default_icon_parents":  "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
}

JAZZMIN_UI_TWEAKS = {
    "navbar_fixed":   True,
    "footer_fixed":   True,
    "sidebar_fixed":  True,
    "sidebar":        "sidebar-dark-navy",
    "theme":          "default",
    "button_classes": {
        "primary":   "btn-primary",
        "success":   "btn-success",
        "info":      "btn-info",
        "warning":   "btn-warning",
        "danger":    "btn-danger",
    },
}


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# PostgreSQL (optional). Set USE_POSTGRES=1 and DB_* in .env to use it.
if os.getenv("USE_POSTGRES") == "1":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME"),
            "USER": os.getenv("DB_USER"),
            "PASSWORD": os.getenv("DB_PASSWORD"),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
        }
    }

# Telegram backup settings (read by backup_db_to_telegram command)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")



# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.sqlite3",
#         "NAME": BASE_DIR / "db.sqlite3",
#     }
# }


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Tashkent'

USE_I18N = True

USE_TZ = True
AUTH_USER_MODEL = 'app.Users'
LOGIN_URL = '/sign-in/'
LOGIN_REDIRECT_URL = '/tests/'
LOGOUT_REDIRECT_URL = '/'

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024

# FFmpeg binary path (audio/video conversion uchun)
# Agar environment da FFMPEG_BIN berilmagan bo'lsa, Ubuntu default yo'lidan foydalanamiz.
FFMPEG_BIN = os.getenv("FFMPEG_BIN", "/usr/bin/ffmpeg")

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
