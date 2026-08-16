from django.urls import path
from .views import experience_view

urlpatterns = [
    path('', experience_view, name='experience'),
]
