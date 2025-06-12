"""
URLs for subscriptions app.
"""
from django.urls import path
from . import views

app_name = 'subscriptions'

urlpatterns = [
    # Subscription plans
    path('plans/', views.SubscriptionPlanListView.as_view(), name='plans'),
    
    # Current subscription
    path('current/', views.CurrentSubscriptionView.as_view(), name='current'),
    
    # Purchase subscription
    path('purchase/', views.PurchaseSubscriptionView.as_view(), name='purchase'),
    
    # Cancel subscription
    path('current/cancel/', views.cancel_subscription, name='cancel'),
    
    # Reactivate subscription
    path('current/reactivate/', views.reactivate_subscription, name='reactivate'),
]