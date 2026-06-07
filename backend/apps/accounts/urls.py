from django.urls import path

from .views import google_signin_view, login_view, logout_view, me_view, onboarding_view, register_view

urlpatterns = [
    path("register/", register_view, name="register"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("me/", me_view, name="me"),
    path("onboarding/", onboarding_view, name="onboarding"),
    path("google-signin/", google_signin_view, name="google-signin"),
]
