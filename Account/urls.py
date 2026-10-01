from django.urls import path
from .views import RegisterView, LoginView, RefreshView,UserListView



urlpatterns = [
    path("register/", RegisterView.as_view()),
    path("login/", LoginView.as_view()),
    path("refresh/", RefreshView.as_view()),
    path("users/", UserListView.as_view()),
    
]

