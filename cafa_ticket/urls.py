from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('djoser.urls')),
    path('api/v1/auth/', include('djoser.urls.jwt')),
    path('api/v1/auth/', include('users.urls')),
    path('api/v1/', include('tickets.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Custom error handlers
handler404 = 'cafa_ticket.error_views.custom_404_view'
handler500 = 'cafa_ticket.error_views.custom_500_view'
handler403 = 'cafa_ticket.error_views.custom_403_view'
handler400 = 'cafa_ticket.error_views.custom_400_view'
