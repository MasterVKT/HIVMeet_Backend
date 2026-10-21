from django.urls import path

from .views import auth, home

app_name = 'backoffice'

urlpatterns = [
    path('', home.HomeView.as_view(), name='home'),
    path('login/', auth.login_view, name='login'),
    path('mfa/', auth.mfa_view, name='mfa'),
    path('logout/', auth.logout_view, name='logout'),
]
