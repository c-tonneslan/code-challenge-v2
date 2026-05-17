from django.conf import settings
from django.contrib import admin
from django.urls import path

from map import views

urlpatterns = [
    path("", views.Home.as_view(), name="home"),
    path("data/", views.DataSummary.as_view(), name="data_summary"),
    path("map-data/", views.MapDataView.as_view(), name="map_data"),
    path("map-data/trends/", views.TrendsView.as_view(), name="trends"),
    path("admin/", admin.site.urls),
    path("robots.txt/", views.robots_txt),
]

handler404 = "map.views.page_not_found"
handler500 = "map.views.server_error"

if settings.DEBUG:
    from django.conf.urls.static import static
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    # Serve static and media files from development server
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
