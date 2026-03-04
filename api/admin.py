"""
Django Admin configuration
"""

from django.contrib import admin
from .models import User, Manufacturer, Product, Batch, QRCode


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['email', 'full_name', 'role', 'city', 'is_active', 'created_at']
    list_filter = ['role', 'is_active', 'city', 'created_at']
    search_fields = ['email', 'full_name', 'phone_number']
    ordering = ['-created_at']


@admin.register(Manufacturer)
class ManufacturerAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'drug_license_number', 'city', 'approval_status', 'created_at']
    list_filter = ['approval_status', 'city', 'created_at']
    search_fields = ['company_name', 'drug_license_number']
    ordering = ['-created_at']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['product_name', 'product_code', 'manufacturer', 'dosage_form', 'strength', 'created_at']
    list_filter = ['dosage_form', 'manufacturer', 'created_at']
    search_fields = ['product_name', 'product_code']
    ordering = ['product_name']


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ['batch_number', 'product', 'manufacturing_date', 'expiry_date', 
                    'batch_status', 'blockchain_status', 'created_at']
    list_filter = ['batch_status', 'blockchain_status', 'unit_type', 'created_at']
    search_fields = ['batch_number', 'product__product_name']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(QRCode)
class QRCodeAdmin(admin.ModelAdmin):
    list_display = ['qr_code_value', 'batch', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['qr_code_value', 'batch__batch_number']
    ordering = ['-created_at']
