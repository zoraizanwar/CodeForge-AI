from django.shortcuts import render
from .models import Education

def education_view(request):
    educations = Education.objects.all()
    return render(request, 'education/education.html', {'educations': educations})
