from django.urls import path
from . import views

app_name = 'returns'

urlpatterns = [
    path('', views.return_list, name='return_list'),
    path('crear/', views.return_create, name='return_create'),
    path('usuarios/crear/', views.user_create, name='user_create'),

    path('api/status-feed/', views.return_status_feed, name='return_status_feed'),
    path('api/live-feed/', views.return_live_feed, name='return_live_feed'),
    path('<int:pk>/observar/', views.return_observe, name='return_observe'),
    path('<int:pk>/enviar-revision/', views.return_send_review, name='return_send_review'),

    path('<int:pk>/', views.return_detail, name='return_detail'),
    path('<int:pk>/editar/', views.return_update, name='return_update'),
    path('<int:pk>/responder/', views.return_respond, name='return_respond'),
    path('<int:pk>/rechazar/', views.return_reject, name='return_reject'),
    path('<int:pk>/cerrar/', views.return_close, name='return_close'),
    
    path('api/<int:pk>/timeline/', views.return_timeline_feed, name='return_timeline_feed'),
]