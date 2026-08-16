from django.db import models

class Education(models.Model):
    degree = models.CharField(max_length=100)
    institute = models.CharField(max_length=200)
    year = models.CharField(max_length=20)

    def __str__(self):
        return self.degree
