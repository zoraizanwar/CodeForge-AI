from django.shortcuts import render
from .models import Bio

def bio_view(request):
    bio = Bio.objects.first()  # assuming single bio entry
    return render(request, 'bio/bio.html', {'bio': bio})
