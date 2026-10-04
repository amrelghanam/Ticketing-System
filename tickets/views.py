from django.utils import timezone
from django.db import transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Ticket,Comment,Attachment,Tag,TicketStatusChange
from Account.models import User
from .serializers import (TagSerializer, TicketSerializer,CommentSerializer,
                         AttachmentSerializer,StatisticSerializer,TopAgentSerializer,
                         TicketListSerializer,TicketStatusChangeSerializer)
from .Permissions import TicketPermission,CommentPermission
from rest_framework.viewsets import ModelViewSet
from rest_framework.generics import ListCreateAPIView,ListAPIView
from rest_framework import status
from django.db.models import Avg,Count,Q,F
from rest_framework.views import APIView




class TicketViewSet(ModelViewSet):
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated, TicketPermission]
    
    def get_serializer_class(self):

        if  self.request.method == "GET":
            return TicketListSerializer

        return TicketSerializer

    def get_queryset(self):

        user = self.request.user
        queryset = (
            Ticket.objects
            .select_related("created_by", "assigned_to")
            .prefetch_related("tags")
            .annotate(comment_count=Count("ticket_comments")).filter(is_deleted=False)
        )
    
        if self.request.user.role == "ADMIN":
            queryset= queryset

        elif self.request.user.role == "AGENT":
            queryset= queryset.filter(
                assigned_to=self.request.user
                
            )
           
        elif self.request.user.role == "USER":
            queryset= queryset.filter(
                created_by=self.request.user
            )
        element_search = {}

        status = self.request.query_params.get("status")
        if status:
              element_search["status"] = status.upper()

        priority = self.request.query_params.get("priority")
        if priority:
           element_search["priority"] = priority.upper()

        assigned_to = self.request.query_params.get("assigned_to")
        if assigned_to:
            element_search["assigned_to_id"] = assigned_to

        queryset = queryset.filter(**element_search)
        
        tags = self.request.query_params.getlist("tag")
        
        if tags:   
            queryset = queryset.filter(
                tags__name__in=tags
           ).distinct()
        
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                  Q(title__icontains=search)
                | Q(description__icontains=search)
            )
        
        role = self.request.query_params.get("role")
        if role:
               queryset = queryset.filter(created_by__role=role)    
        
        ordering = self.request.query_params.get("ordering")

        allowed_ordering = [
            "created_at",
            "-created_at",
            "updated_at",
            "-updated_at",
            "priority",
        ]

        if ordering in allowed_ordering:
            queryset = queryset.order_by(ordering)
        
        return queryset

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user
        )

    def perform_update(self, serializer):

        ticket = serializer.instance
        old_status = ticket.status

        new_status = serializer.validated_data.get("status",old_status)
        with transaction.atomic():
           if old_status != "CLOSED" and new_status == "CLOSED":
              serializer.save(
                closed_at=timezone.now()
            )

           elif old_status == "CLOSED" and new_status != "CLOSED":
              serializer.save(closed_at=None)

           else:
             serializer.save()
           if old_status !=new_status:
                TicketStatusChange.objects.create(
                    ticket=ticket,
                    from_status=old_status,
                    to_status=new_status,
                    changed_by=self.request.user
                    )
                
                
    def destroy(self, request, *args, **kwargs):

        ticket = self.get_object()

        if ticket.ticket_comments.exists():
            return Response(
                {"detail": "Ticket with comments cannot be deleted."},
                status=status.HTTP_409_CONFLICT
            )

        ticket.is_deleted = True
        ticket.save(update_fields=["is_deleted"])

        return Response(status=status.HTTP_204_NO_CONTENT)


class ListCreateCommentView(ListCreateAPIView):

    serializer_class = CommentSerializer
    permission_classes = [CommentPermission]

    def get_queryset(self):
        return Comment.objects.filter(
            ticket_id=self.kwargs["ticket_id"]
        )

    def perform_create(self, serializer):
        serializer.save(
            ticket_id=self.kwargs["ticket_id"],
            user=self.request.user
        )  
        
            
            
class ListCreateAttachmentView(ListCreateAPIView):

    serializer_class = AttachmentSerializer
    permission_classes = [CommentPermission]

    def get_queryset(self):
        return Attachment.objects.filter(
            ticket_id=self.kwargs["ticket_id"]
        )

    def perform_create(self, serializer):
        serializer.save(
            ticket_id=self.kwargs["ticket_id"],
            uploaded_by=self.request.user
        )

                  
class Statistics(APIView):

    def get(self, request):

        ticket_stats = Ticket.objects.aggregate(

            total_ticket=Count("id"),
            open_status=Count("id",filter=Q(status="OPEN")),
            IN_status=Count("id",filter=Q(status="IN_PROGRESS")),
            DONE_status=Count("id",filter=Q(status="DONE")),
            CLOSED_status=Count("id",filter=Q(status="CLOSED")),
            
            low_priority=Count("id",filter=Q(priority="LOW")),
            high_priority=Count("id",filter=Q(priority="HIGH")),
            medium_priority=Count("id",filter=Q(priority="MEDIUM")),
            urgent_priority=Count("id",filter=Q(priority="URGENT")),
            unassigned_ticket=Count("id",filter=Q(assigned_to__isnull=True)),
        )

        avg_result = (Ticket.objects.filter(
                            status="CLOSED",closed_at__isnull=False)
                    .annotate(
                       result=F("closed_at") - F("created_at"))
                    .aggregate(avg_result=Avg("result"))["avg_result"])

        avg_resolution_hours = (
            round(avg_result.total_seconds() / 3600, 2)
            if avg_result
            else 0
        )

        top_agents = (User.objects.filter(role="AGENT")
                     .annotate(count_assigned=Count("assigned_tickets",
                               filter=Q(
                               assigned_tickets__status__in=["OPEN","IN_PROGRESS","DONE"]))
                    ).order_by("-count_assigned")[:1]
                    )

        top_agents_data = TopAgentSerializer(top_agents,many=True).data

        data = {
            "total": ticket_stats["total_ticket"],
            "by_status": {
                "open_status": ticket_stats["open_status"],
                "IN_status": ticket_stats["IN_status"],
                "DONE_status": ticket_stats["DONE_status"],
                "CLOSED_status": ticket_stats["CLOSED_status"],
            },
            "by_priority": {
                "low_priority": ticket_stats["low_priority"],
                "high_priority": ticket_stats["high_priority"],
                "medium_priority": ticket_stats["medium_priority"],
                "urgent_priority": ticket_stats["urgent_priority"],
            },
            "unassigned": ticket_stats["unassigned_ticket"],
            "avg_resolution_hours": avg_resolution_hours,
            "top_agents": top_agents_data,
        }

        serializer = StatisticSerializer(data)

        return Response(serializer.data,status=status.HTTP_200_OK)
    
class TagView(ModelViewSet):
    queryset=Tag.objects.all()
    serializer_class=TagSerializer
    permission_classes=[IsAuthenticated]    
    
    
class HistoryTicket(ListAPIView):
    queryset=TicketStatusChange.objects.all()
    serializer_class=TicketStatusChangeSerializer
    permission_classes=[IsAuthenticated]
    def get_queryset(self):
        return TicketStatusChange.objects.filter(ticket_id=self.kwargs["ticket_id"])   