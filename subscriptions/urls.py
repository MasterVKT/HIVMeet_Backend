"""
URLs for subscriptions app.
"""
from django.urls import path
from . import views
from profiles.kyc import protect_view_with_active_kyc

app_name = 'subscriptions'

urlpatterns = [
    # Subscription plans
    path('plans/', views.SubscriptionPlanListView.as_view(), name='plans'),
    path(
        'payment-capabilities/',
        views.PaymentCapabilitiesView.as_view(),
        name='payment-capabilities',
    ),
    
    # Current subscription
    path('current/', views.CurrentSubscriptionView.as_view(), name='current'),
    
    # Purchase subscription
    path(
        'purchase/',
        protect_view_with_active_kyc(views.PurchaseSubscriptionView.as_view()),
        name='purchase',
    ),
    path(
        'payments/<uuid:payment_id>/',
        views.PaymentStatusView.as_view(),
        name='payment-status',
    ),
    path(
        'payment-return/success/',
        views.payment_return_success,
        name='payment-return-success',
    ),
    path(
        'payment-return/cancel/',
        views.payment_return_cancel,
        name='payment-return-cancel',
    ),
    path(
        'payment-return/failure/',
        views.payment_return_failure,
        name='payment-return-failure',
    ),
    
    # Cancel subscription
    path('current/cancel/', views.cancel_subscription, name='cancel'),
    
    # Reactivate subscription
    path(
        'current/reactivate/',
        protect_view_with_active_kyc(views.reactivate_subscription),
        name='reactivate',
    ),

    # Modify subscription (upgrade/downgrade)
    path(
        'current/modify/',
        protect_view_with_active_kyc(views.modify_subscription),
        name='modify',
    ),
]
