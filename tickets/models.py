from django.db import models
from Account.models import User


class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True) 

class Ticket(models.Model):

    STATUS_CHOICES = (
        ("OPEN", "OPEN"),
        ("IN_PROGRESS", "IN_PROGRESS"),
        ("DONE", "DONE"),
        ("CLOSED", "CLOSED"),
    )

    PRIORITY_CHOICES = (
        ("LOW", "LOW"),
        ("MEDIUM", "MEDIUM"),
        ("HIGH", "HIGH"),
        ("URGENT", "URGENT"),
    )
    

    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20,choices=STATUS_CHOICES,default="OPEN")
    priority = models.CharField(max_length=10,choices=PRIORITY_CHOICES,default="MEDIUM")
    created_by = models.ForeignKey(User,on_delete=models.CASCADE,related_name="created_tickets")
    assigned_to = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True,related_name="assigned_tickets")
    tags = models.ManyToManyField(Tag,blank=True,related_name="tickets")
    closed_at = models.DateTimeField(null=True,blank=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
      indexes = [
        models.Index(fields=["status"]),
        models.Index(fields=["priority"]),
    ]


class Comment(models.Model):
    ticket = models.ForeignKey(Ticket,on_delete=models.PROTECT,related_name="ticket_comments")
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name="user_comments")
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class Attachment(models.Model):
    ticket = models.ForeignKey(Ticket,on_delete=models.CASCADE,related_name="ticket_attachments")
    file = models.FileField()
    uploaded_by = models.ForeignKey(User,on_delete=models.CASCADE,related_name="upload_attachments")
    created_at = models.DateTimeField(auto_now_add=True)



class TicketStatusChange(models.Model):
    ticket = models.ForeignKey(Ticket,on_delete=models.CASCADE,related_name="status_history")
    from_status = models.CharField(max_length=20)
    to_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(User,on_delete=models.CASCADE)
    changed_at = models.DateTimeField(auto_now_add=True)