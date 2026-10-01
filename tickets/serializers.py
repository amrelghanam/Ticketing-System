from pickle import NONE

from django.conf.locale import de
from rest_framework import serializers
from .models import Ticket, Comment, Attachment, Tag,TicketStatusChange
from Account.models import User


class TagSerializer(serializers.ModelSerializer):

    class Meta:
        model = Tag
        fields = ["name"]



class UserShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username"]



class TicketSerializer(serializers.ModelSerializer):

    class Meta:
          model = Ticket
          exclude = ["is_deleted"]
          read_only_fields = [ "created_by","closed_at"]
    def validate_title(self, value):
            if not value:
                raise serializers.ValidationError( "Title cannot be empty." )
            return value 
        
    def validate_description(self, value):
            if not value:
                raise serializers.ValidationError( "Description cannot be empty." )
            return value
        
         
    def validate(self, attrs):
        priority=attrs.get("priority")
        description=attrs.get("description")
        if self.instance:
           priority = attrs.get("priority", self.instance.priority)
           description = attrs.get("description", self.instance.description)

           old_status = self.instance.status
           new_status = attrs.get("status", old_status)

           if old_status == "CLOSED" and new_status == "OPEN":
               raise serializers.ValidationError({
                    "status": "A closed ticket cannot be reopened."})
         
         #URGENT requires at least 30 characters
        if priority == "URGENT" and len(description) < 30:
            raise serializers.ValidationError(
                { "description": "URGENT tickets must have at least 30 characters." })
          
         #assigned_to must be AGENT or ADMIN 
        assigned_to = attrs.get("assigned_to")
        if assigned_to: 
            if assigned_to.role not in ["AGENT", "ADMIN"]:
                raise serializers.ValidationError(
                    { "assigned_to": "Ticket can only be assigned to an agent or admin." })
        return attrs   
    
#for list payload 
class TicketListSerializer(serializers.ModelSerializer):

    created_by = UserShortSerializer(read_only=True)
    assigned_to = UserShortSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    comment_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Ticket
        exclude = ["description","is_deleted","updated_at"]


class CommentSerializer(serializers.ModelSerializer):

    class Meta:
        model = Comment
        fields = "__all__"
        read_only_fields = ["ticket","user","created_at",]

    def validate_text(self, value):
                if not value: 
                    raise serializers.ValidationError( "comment cannot be empty." )
                return value

class AttachmentSerializer(serializers.ModelSerializer):

    class Meta:
        model = Attachment
        fields = "__all__"
        read_only_fields = ["ticket","uploaded_by","created_at",]

    def validate_file(self, value):
        max_size = 5 * 1024 * 1024
        if value.size > max_size: 
            raise serializers.ValidationError( "File size cannot exceed 5 MB." ) 
    
        allowed_extensions = [ "png", "jpg", "jpeg", "pdf", "txt", "log"] 
        file_name = value.name.lower()
        if "." not in file_name:
            raise serializers.ValidationError( "File must have an extension." )
        extension = file_name.split(".")[-1]
        if extension not in allowed_extensions:
            raise serializers.ValidationError( "Unsupported file type." ) 
        return value
    
    
class TopAgentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    count_assigned = serializers.IntegerField()

    
class StatisticSerializer(serializers.Serializer):
      total =serializers.IntegerField()
      by_status=serializers.DictField()    
      by_priority=serializers.DictField()
      unassigned=serializers.IntegerField()
      avg_resolution_hours =serializers.DecimalField(max_digits=10,decimal_places=2)
      top_agents=TopAgentSerializer(many=True)
   
      
class TicketStatusChangeSerializer(serializers.ModelSerializer):
    changed_by = UserShortSerializer(read_only=True)
    class Meta:
        model = TicketStatusChange
        fields ="__all__"
          