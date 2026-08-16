from django.shortcuts import render

from bio.models import Bio
from education.models import Education
from skills.models import Skill
from experience.models import Experience
from projects.models import Project

def home_view(request):
    context = {
        "bios": Bio.objects.all(),
        "educations": Education.objects.all(),
        "skills": Skill.objects.all(),
        "experiences": Experience.objects.all(),
        "projects": Project.objects.all(),
    }
    return render(request, "core/home.html", context)
