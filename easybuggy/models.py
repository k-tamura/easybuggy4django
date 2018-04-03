from django.db import models


class User(models.Model):
    id = models.CharField(max_length=10, primary_key=True)
    name = models.CharField(max_length=30)
    password = models.CharField(max_length=30)
    secret = models.CharField(max_length=100)
    ispublic = models.CharField(max_length=5)
    phone = models.CharField(max_length=20, blank=True, null=True)
    mail = models.EmailField(max_length=100, blank=True, null=True)
