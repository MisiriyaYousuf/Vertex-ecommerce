from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):

    user = models.OneToOneField(User, on_delete=models.CASCADE,related_name='profile')
    phone = models.CharField(max_length=10, blank=False, null=False,unique=True)
    profile_image = models.ImageField(upload_to='profile_images/',blank=True,null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    blocked = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}'s Profile"


class Address(models.Model):

    ADDRESS_TYPE_CHOICES = [
        ('Home', 'Home'),
        ('Office', 'Office'),
        ('Apartment', 'Apartment'),
        ('Others', 'Others'),
    ]

    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name='addresses')
    country = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    address_type = models.CharField(max_length=20,choices=ADDRESS_TYPE_CHOICES)
    building = models.CharField(max_length=255)
    area = models.CharField(max_length=255)
    landmark = models.CharField(max_length=255,blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.address_type}"

class OTP(models.Model):
   
    email = models.EmailField()
    otp_hash = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_verified = models.BooleanField(default=False)
    is_used = models.BooleanField(default=False)
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_verified", "is_used"]),
            models.Index(fields=["expires_at"])
        ]

    def __str__(self):
        status = "Verified" if self.is_verified else "Pending"
        return f"OTP for {self.email} - {status}"

