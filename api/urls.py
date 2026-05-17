"""
URL routing for API endpoints
"""

from django.urls import path
from . import views

urlpatterns = [
    path('', views.api_root, name='api_root'),
    # Authentication
    path('auth/register', views.register, name='register'),
    path('auth/login', views.login, name='login'),
    
    # Manufacturer
    path('manufacturers/profile', views.manufacturer_profile, name='manufacturer_profile'),
    path('manufacturers', views.manufacturer_list, name='manufacturer_list'),
    path('manufacturers/register', views.manufacturer_register, name='manufacturer_register'),
    path('manufacturers/approve', views.manufacturer_approve, name='manufacturer_approve'),
    path('manufacturers/deactivate', views.manufacturer_deactivate, name='manufacturer_deactivate'),
    path('manufacturers/<uuid:id>', views.manufacturer_detail, name='manufacturer_detail'),
    
    # Product
    path('products', views.product_list, name='product_list'),
    path('products/create', views.product_create, name='product_create'),
    
    # Batch
    path('batches', views.batch_list, name='batch_list'),
    path('batches/create', views.batch_create, name='batch_create'),
    path('batches/<uuid:id>', views.batch_detail, name='batch_detail'),
    path('batches/<uuid:id>/dispatch',   views.batch_dispatch,   name='batch_dispatch'),
    path('batches/<uuid:id>/dispatches', views.batch_dispatches, name='batch_dispatches'),
    path('batches/<uuid:batch_id>/traceability', views.batch_traceability, name='batch_traceability'),
    path('batches/<uuid:id>/recall',     views.batch_recall,     name='batch_recall'),
    path('inventory',                    views.inventory,         name='inventory'),
    path('batches/<uuid:batchId>/qr-codes', views.batch_qr_codes, name='batch_qr_codes'),
    path('batches/<uuid:batchId>/generate-qr', views.batch_generate_qr, name='batch_generate_qr'),
    
    # Chatbot
    path('chatbot', views.chatbot, name='chatbot'),

    # QR Verification
    path('verify/qr', views.verify_qr, name='verify_qr'),
    path('verify/qr/trace', views.trace_qr, name='trace_qr'),

    # Scan Logs & Alerts
    path('scan-logs', views.scan_logs, name='scan_logs'),
    path('counterfeit-alerts', views.counterfeit_alerts, name='counterfeit_alerts'),

    # Pharmacy
    path('pharmacy/profile', views.pharmacy_profile, name='pharmacy_profile'),
    path('pharmacy/register', views.pharmacy_register, name='pharmacy_register'),
    path('pharmacy/approve', views.pharmacy_approve, name='pharmacy_approve'),
    path('pharmacy/deactivate', views.pharmacy_deactivate, name='pharmacy_deactivate'),
    path('pharmacies', views.pharmacy_list, name='pharmacy_list'),

    # Distributor
    path('distributor/profile', views.distributor_profile, name='distributor_profile'),
    path('distributor/register', views.distributor_register, name='distributor_register'),
    path('distributor/approve', views.distributor_approve, name='distributor_approve'),
    path('distributor/deactivate', views.distributor_deactivate, name='distributor_deactivate'),
    path('distributors', views.distributor_list, name='distributor_list'),
]

