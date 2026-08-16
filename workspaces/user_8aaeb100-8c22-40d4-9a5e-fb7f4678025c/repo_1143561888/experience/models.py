from django.db import models

# Create your models here.
class Experience(models.Model):
    title = models.CharField(max_length=100)
    organization = models.CharField(max_length=200)
    description = models.TextField()

    def __str__(self):
        return self.title
