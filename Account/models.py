from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    ROLE_CHOICES = (
        ("ADMIN", "ADMIN"),
        ("AGENT", "AGENT"),
        ("USER", "USER"),
    )

    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES
    )

