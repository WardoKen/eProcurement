from pathlib import Path

from django.conf import settings
from django.urls import include, path
from django.views.static import serve

urlpatterns = [
    path('api/', include('api.urls')),
    path(
        'uploads/<path:path>',
        serve,
        {
            'document_root': str(Path(settings.BASE_DIR) / 'uploads'),
        },
    ),
]
