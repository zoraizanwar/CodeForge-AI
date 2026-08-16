from django.shortcuts import render
from .models import Experience

def experience_view(request):
    experiences = Experience.objects.all()
    return render(request, 'experience/experience.html', {'experiences': experiences})
