from django.urls import path
from .views import bio_view

urlpatterns = [
    path('', bio_view, name='bio'),
]
