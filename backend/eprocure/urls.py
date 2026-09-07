from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.static import serve

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
    path(
        "uploads/<path:path>",
        # Exempt from X-Frame-Options so generated PDFs (e.g. the RFQ preview)
        # can be embedded in an <iframe> from the frontend origin.
        xframe_options_exempt(serve),
        {
            "document_root": str(Path(settings.BASE_DIR) / "uploads"),
        },
    ),
]