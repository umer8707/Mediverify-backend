"""
URL routing for API endpoints
"""

from django.urls import path
from . import views

urlpatterns = [
    # Authentication
    path('auth/register', views.register, name='register'),
    path('auth/login', views.login, name='login'),
    
    # Manufacturer
    path('manufacturers/register', views.manufacturer_register, name='manufacturer_register'),
    path('manufacturers/approve', views.manufacturer_approve, name='manufacturer_approve'),
    
    # Product
    path('products/create', views.product_create, name='product_create'),
    
    # Batch
    path('batches', views.batch_list, name='batch_list'),
    path('batches/create', views.batch_create, name='batch_create'),
    path('batches/<uuid:id>', views.batch_detail, name='batch_detail'),
    path('batches/<uuid:batchId>/generate-qr', views.batch_generate_qr, name='batch_generate_qr'),
    
    # QR Verification
    path('verify/qr', views.verify_qr, name='verify_qr'),
]

