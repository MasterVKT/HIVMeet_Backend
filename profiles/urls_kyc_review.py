"""Restricted internal KYC review routes."""

from django.urls import path

from . import views


urlpatterns = [
    path('mfa/enroll/', views.kyc_reviewer_mfa_enroll_view),
    path('mfa/confirm/', views.kyc_reviewer_mfa_confirm_view),
    path('mfa/assertions/', views.kyc_reviewer_mfa_verify_view),
    path('cases/', views.kyc_review_case_list_view),
    path('cases/unassigned/', views.kyc_review_unassigned_case_list_view),
    path('cases/<uuid:case_id>/assignment/', views.assign_kyc_review_case_view),
    path('cases/<uuid:case_id>/', views.kyc_review_case_detail_view),
    path('cases/<uuid:case_id>/documents/<uuid:document_id>/access/', views.issue_kyc_review_document_url_view),
    path('cases/<uuid:case_id>/documents/<uuid:document_id>/development-content/', views.read_kyc_review_document_development_view),
    path('cases/<uuid:case_id>/decision/', views.decide_kyc_review_case_view),
]
