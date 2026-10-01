from django.shortcuts import get_object_or_404
from rest_framework.permissions import BasePermission

from .models import Ticket


class TicketPermission(BasePermission):

    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user = request.user

        # Admin can do everything
        if user.role == "ADMIN":
            return True

        # Agent can access only assigned tickets
        if user.role == "AGENT":
            if obj.assigned_to_id != user.id:
                return False

            return True

        # Regular user can access only tickets created by him
        if user.role == "USER":
            if obj.created_by_id != user.id:
                return False

            # User cannot change status
            if request.method in ["PUT", "PATCH"]and "status" in request.data:
                return False

            # User cannot change assigned_to
            if request.method in ["PUT", "PATCH"]and "assigned_to" in request.data:
                return False

            return True

        return False


class CommentPermission(BasePermission):

    def has_permission(self, request, view):
        # Authentication is required
        if not request.user.is_authenticated:
            return False

        
        ticket = get_object_or_404(Ticket,id=view.kwargs["ticket_id"])

        # Admin can access all comments
        if request.user.role == "ADMIN":
            return True

        # Agent can access comments of assigned tickets
        if request.user.role == "AGENT":
            return ticket.assigned_to == request.user

        # User can access comments of created tickets
        if request.user.role == "USER":
            return ticket.created_by == request.user

        return False
    
    
    
    
    
