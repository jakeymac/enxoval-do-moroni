from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path, re_path
from django.views.generic import TemplateView

from registry.views import healthz


class SPAView(TemplateView):
    """Serves the built React app. Missing before `npm run build` has ever run."""

    template_name = "index.html"

    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except Exception:
            return HttpResponse(
                "<h1>Frontend not built</h1><p>Run <code>npm run build</code> in "
                "<code>frontend/</code>, or use the Vite dev server at "
                "<a href='http://localhost:5173'>localhost:5173</a>.</p>",
                status=501,
            )


urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("api/", include("registry.urls")),
    # Everything else is a React route (/ and the owner's area under ADMIN_PATH).
    re_path(r"^(?!api/|admin/|static/|healthz).*$", SPAView.as_view()),
]
