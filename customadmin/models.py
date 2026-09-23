from django.db import models
from django.contrib.auth.models import User

class user_details(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    blocked = models.BooleanField(default=False)  
    def __str__(self):
        return self.user.username
    
class Category(models.Model):

    name = models.CharField(max_length=100, unique=True)
    is_trashed = models.BooleanField(default=False)
    trashed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name
