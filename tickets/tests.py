from django.test import TestCase
from datetime import timedelta
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase

from Account.models import User

from .models import Ticket,Comment,Attachment,Tag,TicketStatusChange

class TicketTests(APITestCase):

    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin",
            password="123456",
            role="ADMIN",
        )

        self.agent = User.objects.create_user(
            username="agent",
            password="123456",
            role="AGENT",
        )

        self.agent2 = User.objects.create_user(
            username="agent2",
            password="123456",
            role="AGENT",
        )

        self.user = User.objects.create_user(
            username="user",
            password="123456",
            role="USER",
        )

        self.user2 = User.objects.create_user(
            username="user2",
            password="123456",
            role="USER",
        )

        self.tag = Tag.objects.create(name="Bug")

        self.ticket = Ticket.objects.create(
            title="Printer problem",
            description="Printer is not working",
            created_by=self.user,
            assigned_to=self.agent,
            priority="MEDIUM",
        )

        self.ticket.tags.add(self.tag)

    # AUTHENTICATION
        
    def test_unauthenticated_user_cannot_access_tickets(self):
        self.client.force_authenticate(user=None)

        response = self.client.get("/ticket/")

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    # ROLE FILTERING
    def test_user_sees_only_own_tickets(self):
        Ticket.objects.create(
            title="Other ticket",
            description="Other user ticket",
            created_by=self.user2,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get("/ticket/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = response.data["results"]

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], self.ticket.id)

    def test_agent_sees_only_assigned_tickets(self):
        other_ticket = Ticket.objects.create(
            title="Other ticket",
            description="Not assigned to agent",
            created_by=self.user2,
            assigned_to=self.agent2,
        )

        self.client.force_authenticate(user=self.agent)

        response = self.client.get("/ticket/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        ids = [ticket["id"] for ticket in response.data["results"]]

        self.assertIn(self.ticket.id, ids)
        self.assertNotIn(other_ticket.id, ids)

    def test_admin_can_see_all_tickets(self):
        other_ticket = Ticket.objects.create(
            title="Admin ticket",
            description="Admin can see this",
            created_by=self.user2,
        )

        self.client.force_authenticate(user=self.admin)

        response = self.client.get("/ticket/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        ids = [ticket["id"] for ticket in response.data["results"]]

        self.assertIn(self.ticket.id, ids)
        self.assertIn(other_ticket.id, ids)

    # CREATE    
    def test_created_by_is_authenticated_user(self):
        self.client.force_authenticate(user=self.user)

        data = {
            "title": "New ticket",
            "description": "Created by authenticated user",
        }

        response = self.client.post(
            "/ticket/",
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        ticket = Ticket.objects.get(
            title="New ticket"
        )

        self.assertEqual(
            ticket.created_by,
            self.user,
        )

    # VALIDATION
    
    def test_urgent_ticket_requires_30_characters(self):
        self.client.force_authenticate(user=self.user)

        data = {
            "title": "Urgent ticket",
            "description": "Too short",
            "priority": "URGENT",
        }

        response = self.client.post(
            "/ticket/",
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_urgent_ticket_with_long_description_is_valid(self):
        self.client.force_authenticate(user=self.user)

        data = {
            "title": "Urgent ticket",
            "description": (
                "This is a long description containing "
                "more than thirty characters."
            ),
            "priority": "URGENT",
        }

        response = self.client.post(
            "/ticket/",
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

    def test_assigned_to_must_be_agent_or_admin(self):
        self.client.force_authenticate(user=self.user)

        data = {
            "title": "Invalid assignment",
            "description": "Testing assigned user validation",
            "assigned_to": self.user2.id,
        }

        response = self.client.post(
            "/ticket/",
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    
    # UPDATE PERMISSIONS

    def test_regular_user_cannot_change_status(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            f"/ticket/{self.ticket.id}/",
            {"status": "DONE"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_regular_user_cannot_change_assigned_to(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            f"/ticket/{self.ticket.id}/",
            {"assigned_to": self.agent2.id},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_other_user_cannot_update_ticket(self):
        self.client.force_authenticate(user=self.user2)

        response = self.client.patch(
            f"/ticket/{self.ticket.id}/",
            {"title": "Hacked title"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    # AGENT STATUS
    
    def test_assigned_agent_can_move_ticket_to_done(self):
        self.client.force_authenticate(user=self.agent)

        response = self.client.patch(
            f"/ticket/{self.ticket.id}/",
            {"status": "DONE"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.ticket.refresh_from_db()

        self.assertEqual(
            self.ticket.status,
            "DONE",
        )

    def test_unassigned_agent_cannot_update_ticket(self):
        self.client.force_authenticate(user=self.agent2)

        response = self.client.patch(
            f"/ticket/{self.ticket.id}/",
            {"status": "DONE"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    # CLOSED / CLOSED_AT
    
    def test_closed_ticket_cannot_be_reopened(self):
        self.ticket.status = "CLOSED"
        self.ticket.closed_at = timezone.now()
        self.ticket.save()

        self.client.force_authenticate(user=self.agent)

        response = self.client.patch(
            f"/ticket/{self.ticket.id}/",
            {"status": "OPEN"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_closed_at_is_set_when_ticket_is_closed(self):
        self.client.force_authenticate(user=self.agent)

        response = self.client.patch(
            f"/ticket/{self.ticket.id}/",
            {"status": "CLOSED"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.ticket.refresh_from_db()

        self.assertEqual(
            self.ticket.status,
            "CLOSED",
        )

        self.assertIsNotNone(
            self.ticket.closed_at
        )

    def test_closed_at_is_cleared_when_leaving_closed(self):
        self.ticket.status = "CLOSED"
        self.ticket.closed_at = timezone.now()
        self.ticket.save()

        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f"/ticket/{self.ticket.id}/",
            {"status": "DONE"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.ticket.refresh_from_db()

        self.assertIsNone(
            self.ticket.closed_at
        )
        
    # STATUS HISTORY
    
    def test_status_change_creates_history(self):
        self.client.force_authenticate(user=self.agent)

        response = self.client.patch(
            f"/ticket/{self.ticket.id}/",
            {"status": "DONE"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        history = TicketStatusChange.objects.filter(
            ticket=self.ticket
        )

        self.assertEqual(
            history.count(),
            1,
        )

        self.assertEqual(
            history.first().from_status,
            "OPEN",
        )

        self.assertEqual(
            history.first().to_status,
            "DONE",
        )

        self.assertEqual(
            history.first().changed_by,
            self.agent,
        )

    def test_same_status_does_not_create_history(self):
        self.client.force_authenticate(user=self.agent)

        response = self.client.patch(
            f"/ticket/{self.ticket.id}/",
            {"status": "OPEN"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            TicketStatusChange.objects.filter(
                ticket=self.ticket
            ).count(),
            0,
        )

    def test_history_endpoint(self):
        TicketStatusChange.objects.create(
            ticket=self.ticket,
            from_status="OPEN",
            to_status="DONE",
            changed_by=self.agent,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/ticket/{self.ticket.id}/history"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            1,
        )

    # DELETE / SOFT DELETE
    
    def test_ticket_with_comments_cannot_be_deleted(self):
        Comment.objects.create(
            ticket=self.ticket,
            user=self.user,
            text="Important comment",
        )

        self.client.force_authenticate(user=self.admin)

        response = self.client.delete(
            f"/ticket/{self.ticket.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
        )

        self.ticket.refresh_from_db()

        self.assertFalse(
            self.ticket.is_deleted
        )

    def test_ticket_without_comments_is_soft_deleted(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.delete(
            f"/ticket/{self.ticket.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.ticket.refresh_from_db()

        self.assertTrue(
            self.ticket.is_deleted
        )

    def test_deleted_ticket_not_in_ticket_list(self):
        self.ticket.is_deleted = True
        self.ticket.save()

        self.client.force_authenticate(user=self.user)

        response = self.client.get("/ticket/")

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        ids = [
            ticket["id"]
            for ticket in response.data["results"]
        ]

        self.assertNotIn(
            self.ticket.id,
            ids,
        )

    # FILTERING-
    
    def test_status_filter(self):
        self.ticket.status = "DONE"
        self.ticket.save()

        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            "/ticket/?status=DONE"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        for ticket in response.data["results"]:
            self.assertEqual(
                ticket["status"],
                "DONE",
            )

    def test_priority_filter(self):
        self.ticket.priority = "HIGH"
        self.ticket.save()

        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            "/ticket/?priority=HIGH"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        for ticket in response.data["results"]:
            self.assertEqual(
                ticket["priority"],
                "HIGH",
            )

    def test_assigned_to_filter(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            f"/ticket/?assigned_to={self.agent.id}"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        for ticket in response.data["results"]:
            self.assertEqual(
                ticket["assigned_to"]["id"],
                self.agent.id,
            )

    def test_tag_filter(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            "/ticket/?tag=Bug"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        ids = [
            ticket["id"]
            for ticket in response.data["results"]
        ]

        self.assertIn(
            self.ticket.id,
            ids,
        )

   
    def test_search_by_title(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            "/ticket/?search=Printer"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        ids = [
            ticket["id"]
            for ticket in response.data["results"]
        ]

        self.assertIn(
            self.ticket.id,
            ids,
        )

    def test_search_by_description(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            "/ticket/?search=not working"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        ids = [
            ticket["id"]
            for ticket in response.data["results"]
        ]

        self.assertIn(
            self.ticket.id,
            ids,
        )

  

    def test_ordering(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            "/ticket/?ordering=-created_at"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_invalid_ordering_is_ignored(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            "/ticket/?ordering=password"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        
 

    def test_ticket_list_is_paginated(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/ticket/")

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertIn(
            "results",
            response.data,
        )

        self.assertIn(
            "count",
            response.data,
        )

    
  

    def test_ticket_list_contains_required_fields(self):
        Comment.objects.create(
            ticket=self.ticket,
            user=self.user,
            text="Test comment",
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get("/ticket/")

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        ticket = response.data["results"][0]

        required_fields = [
            "id",
            "title",
            "status",
            "priority",
            "created_by",
            "assigned_to",
            "comment_count",
            "tags",
            "created_at",
        ]

        for field in required_fields:
            self.assertIn(
                field,
                ticket,
            )

    

    def test_user_can_list_own_ticket_comments(self):
        Comment.objects.create(
            ticket=self.ticket,
            user=self.user,
            text="My comment",
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/ticket/{self.ticket.id}/comment/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_user_can_create_comment(self):
        self.client.force_authenticate(user=self.user)

        data = {
            "text": "This is a new comment"
        }

        response = self.client.post(
            f"/api/ticket/{self.ticket.id}/comment/",
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        comment = Comment.objects.get(
            ticket=self.ticket,
            text="This is a new comment",
        )

        self.assertEqual(
            comment.user,
            self.user,
        )

    def test_other_user_cannot_access_ticket_comments(self):
        self.client.force_authenticate(user=self.user2)

        response = self.client.get(
            f"/api/ticket/{self.ticket.id}/comment/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    # ATTACHMENTS--

    def test_user_can_upload_attachment(self):
        self.client.force_authenticate(user=self.user)

        file = SimpleUploadedFile(
            "test.txt",
            b"hello world",
            content_type="text/plain",
        )

        response = self.client.post(
            f"/api/ticket/{self.ticket.id}/attachment/",
            {"file": file},
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        attachment = Attachment.objects.get(
            ticket=self.ticket
        )

        self.assertEqual(
            attachment.uploaded_by,
            self.user,
        )

    def test_attachment_with_invalid_extension_is_rejected(self):
        self.client.force_authenticate(user=self.user)

        file = SimpleUploadedFile(
            "malware.exe",
            b"fake file",
            content_type="application/octet-stream",
        )

        response = self.client.post(
            f"/api/ticket/{self.ticket.id}/attachment/",
            {"file": file},
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_attachment_larger_than_5_mb_is_rejected(self):
        self.client.force_authenticate(user=self.user)

        large_file = SimpleUploadedFile(
            "large.txt",
            b"x" * (5 * 1024 * 1024 + 1),
            content_type="text/plain",
        )

        response = self.client.post(
            f"/api/ticket/{self.ticket.id}/attachment/",
            {"file": large_file},
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
    

    def test_statistics_endpoint(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            "/api/tickets/stats/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertIn(
            "total",
            response.data,
        )

        self.assertIn(
            "by_status",
            response.data,
        )

        self.assertIn(
            "by_priority",
            response.data,
        )

        self.assertIn(
            "unassigned",
            response.data,
        )

        self.assertIn(
            "avg_resolution_hours",
            response.data,
        )

        self.assertIn(
            "top_agents",
            response.data,
        )

    def test_deleted_tickets_not_in_statistics(self):
        Ticket.objects.all().delete()

        active_ticket = Ticket.objects.create(
            title="Active",
            description="Active ticket",
            created_by=self.user
        )

        Ticket.objects.create(
              title="Deleted",
              description="Deleted ticket",
              created_by=self.user,
              is_deleted=True
            )

        response = self.client.get("/api/tickets/stats/")

        print(response.data)

    # QUERY COUNT / N+1-

    def test_ticket_list_query_count(self):
        self.client.force_authenticate(user=self.admin)

        # Create enough data to expose N+1 problems.
        for i in range(10):
            ticket = Ticket.objects.create(
                title=f"Query ticket {i}",
                description="Testing query optimization",
                created_by=self.user,
                assigned_to=self.agent,
            )

            ticket.tags.add(self.tag)

            Comment.objects.create(
                ticket=ticket,
                user=self.user,
                text="Test comment",
            )

     
        with self.assertNumQueries(3):
            response = self.client.get("/ticket/")

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertIn(
            "results",
            response.data,
        )
        
