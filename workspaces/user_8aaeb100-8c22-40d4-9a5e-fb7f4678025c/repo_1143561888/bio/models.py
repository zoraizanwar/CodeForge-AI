from django.db import models

class Bio(models.Model):
    name = models.CharField(max_length=100)
    job_title = models.CharField(max_length=100)
    profile_image = models.ImageField(upload_to='profile/')
    description = models.TextField()

    def __str__(self):
        return self.name
