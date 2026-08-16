from django.db import models

# Create your models here.
class Skill(models.Model):
    skill_name = models.CharField(max_length=100)
    level = models.CharField(max_length=50)

    def __str__(self):
        return self.skill_name
