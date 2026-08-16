from django.urls import path
from .views import skills_view

urlpatterns = [
    path('', skills_view, name='skills'),
]
