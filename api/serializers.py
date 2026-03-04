"""
Serializers for API endpoints
"""

from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User, Manufacturer, Product, Batch, QRCode


class UserSerializer(serializers.ModelSerializer):
    """User serializer for registration and profile"""
    
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    
    class Meta:
        model = User
        fields = ['id', 'full_name', 'email', 'password', 'role', 'phone_number', 
                  'city', 'country', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']
        extra_kwargs = {
            'password': {'write_only': True}
        }
    
    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            full_name=validated_data['full_name'],
            role=validated_data['role'],
            phone_number=validated_data.get('phone_number', ''),
            city=validated_data.get('city', 'Lahore'),
            country=validated_data.get('country', 'Pakistan'),
        )
        return user


class UserLoginSerializer(serializers.Serializer):
    """Login serializer"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class ManufacturerSerializer(serializers.ModelSerializer):
    """Manufacturer serializer"""
    user = UserSerializer(read_only=True)
    user_id = serializers.UUIDField(write_only=True, required=False)
    
    class Meta:
        model = Manufacturer
        fields = ['id', 'user', 'user_id', 'company_name', 'drug_license_number',
                  'manufacturing_address', 'city', 'country', 'approval_status',
                  'approved_by', 'approved_at', 'created_at']
        read_only_fields = ['id', 'approved_by', 'approved_at', 'created_at']


class ManufacturerApprovalSerializer(serializers.Serializer):
    """Manufacturer approval serializer"""
    manufacturer_id = serializers.UUIDField()
    approval_status = serializers.ChoiceField(choices=['APPROVED', 'REJECTED'])


class ProductSerializer(serializers.ModelSerializer):
    """Product serializer"""
    manufacturer_name = serializers.CharField(source='manufacturer.company_name', read_only=True)
    
    class Meta:
        model = Product
        fields = ['id', 'manufacturer', 'manufacturer_name', 'product_name', 'product_code',
                  'dosage_form', 'strength', 'description', 'created_at']
        read_only_fields = ['id', 'created_at']


class BatchSerializer(serializers.ModelSerializer):
    """Batch serializer - most important model"""
    product_name = serializers.CharField(source='product.product_name', read_only=True)
    product_code = serializers.CharField(source='product.product_code', read_only=True)
    manufacturer_name = serializers.CharField(source='product.manufacturer.company_name', read_only=True)
    
    class Meta:
        model = Batch
        fields = ['id', 'product', 'product_name', 'product_code', 'manufacturer_name',
                  'batch_number', 'manufacturing_date', 'expiry_date', 'quantity_manufactured',
                  'unit_type', 'manufacturing_site', 'quality_certification_code',
                  'storage_conditions', 'mrp_price', 'distribution_region', 'batch_status',
                  'blockchain_tx_hash', 'blockchain_status', 'created_at', 'updated_at']
        # blockchain_tx_hash and blockchain_status are read-only placeholders for future integration
        read_only_fields = ['id', 'created_at', 'updated_at', 'blockchain_tx_hash', 'blockchain_status']


class QRCodeSerializer(serializers.ModelSerializer):
    """QR Code serializer"""
    batch_number = serializers.CharField(source='batch.batch_number', read_only=True)
    product_name = serializers.CharField(source='batch.product.product_name', read_only=True)
    
    class Meta:
        model = QRCode
        fields = ['id', 'batch', 'batch_number', 'product_name', 'qr_code_value',
                  'is_active', 'created_at']
        read_only_fields = ['id', 'qr_code_value', 'created_at']


class QRVerificationSerializer(serializers.Serializer):
    """QR Code verification request serializer"""
    qr_code_value = serializers.CharField(required=True)
    scanned_by_role = serializers.ChoiceField(
        choices=['CONSUMER', 'PHARMACY', 'DISTRIBUTOR', 'MANUFACTURER'],
        required=True
    )
    scan_location_city = serializers.CharField(required=True)
    scan_location_country = serializers.CharField(required=False, default='Pakistan')
    device_type = serializers.ChoiceField(
        choices=['WEB', 'ANDROID', 'IOS'],
        required=True
    )


class QRVerificationResponseSerializer(serializers.Serializer):
    """QR Code verification response serializer"""
    verification_result = serializers.CharField()
    batch_id = serializers.UUIDField(required=False)
    batch_number = serializers.CharField(required=False)
    product_name = serializers.CharField(required=False)
    manufacturing_date = serializers.DateField(required=False)
    expiry_date = serializers.DateField(required=False)
    message = serializers.CharField()

