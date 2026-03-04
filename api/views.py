"""
API Views for Pharmaceutical Product Verification System
"""

import secrets
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from django.db import transaction

from .models import User, Manufacturer, Product, Batch, QRCode
from .serializers import (
    UserSerializer, UserLoginSerializer, ManufacturerSerializer,
    ManufacturerApprovalSerializer, ProductSerializer, BatchSerializer,
    QRCodeSerializer, QRVerificationSerializer, QRVerificationResponseSerializer
)
from .mongodb_client import mongodb_client
# Note: Blockchain integration is intentionally deferred for future implementation
# The Batch model includes blockchain_tx_hash and blockchain_status fields as placeholders

# ==================== AUTHENTICATION ====================

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register(request):
    """
    POST /auth/register
    Register a new user
    """
    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            'message': 'User registered successfully',
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login(request):
    """
    POST /auth/login
    Login user and return JWT tokens
    """
    serializer = UserLoginSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        
        try:
            user = User.objects.get(email=email)
            if user.check_password(password) and user.is_active:
                refresh = RefreshToken.for_user(user)
                return Response({
                    'message': 'Login successful',
                    'user': UserSerializer(user).data,
                    'tokens': {
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                    }
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': 'Invalid credentials or inactive account'
                }, status=status.HTTP_401_UNAUTHORIZED)
        except User.DoesNotExist:
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== MANUFACTURER ====================

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def manufacturer_register(request):
    """
    POST /manufacturers/register
    Register a manufacturer profile (requires MANUFACTURER role)
    """
    if request.user.role != 'MANUFACTURER':
        return Response({
            'error': 'Only users with MANUFACTURER role can register as manufacturer'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Check if manufacturer profile already exists
    if hasattr(request.user, 'manufacturer_profile'):
        return Response({
            'error': 'Manufacturer profile already exists'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    serializer = ManufacturerSerializer(data=request.data)
    if serializer.is_valid():
        manufacturer = serializer.save(user=request.user)
        return Response({
            'message': 'Manufacturer profile registered successfully. Waiting for approval.',
            'manufacturer': ManufacturerSerializer(manufacturer).data
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def manufacturer_approve(request):
    """
    POST /manufacturers/approve
    Approve or reject a manufacturer (requires ADMIN role)
    """
    if request.user.role != 'ADMIN':
        return Response({
            'error': 'Only ADMIN users can approve manufacturers'
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = ManufacturerApprovalSerializer(data=request.data)
    if serializer.is_valid():
        manufacturer_id = serializer.validated_data['manufacturer_id']
        approval_status = serializer.validated_data['approval_status']
        
        try:
            manufacturer = Manufacturer.objects.get(id=manufacturer_id)
            manufacturer.approval_status = approval_status
            manufacturer.approved_by = request.user
            manufacturer.approved_at = timezone.now()
            manufacturer.save()
            
            return Response({
                'message': f'Manufacturer {approval_status.lower()} successfully',
                'manufacturer': ManufacturerSerializer(manufacturer).data
            }, status=status.HTTP_200_OK)
        except Manufacturer.DoesNotExist:
            return Response({
                'error': 'Manufacturer not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== PRODUCT ====================

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def product_create(request):
    """
    POST /products/create
    Create a new product (requires approved MANUFACTURER)
    """
    # Check if user is a manufacturer
    if request.user.role != 'MANUFACTURER':
        return Response({
            'error': 'Only manufacturers can create products'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Check if manufacturer is approved
    try:
        manufacturer = request.user.manufacturer_profile
        if manufacturer.approval_status != 'APPROVED':
            return Response({
                'error': 'Manufacturer must be approved before creating products'
            }, status=status.HTTP_403_FORBIDDEN)
    except Manufacturer.DoesNotExist:
        return Response({
            'error': 'Manufacturer profile not found. Please register first.'
        }, status=status.HTTP_404_NOT_FOUND)
    
    serializer = ProductSerializer(data=request.data)
    if serializer.is_valid():
        product = serializer.save(manufacturer=manufacturer)
        return Response({
            'message': 'Product created successfully',
            'product': ProductSerializer(product).data
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== BATCH ====================

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def batch_create(request):
    """
    POST /batches/create
    Create a new batch (requires approved MANUFACTURER)
    """
    # Check if user is a manufacturer
    if request.user.role != 'MANUFACTURER':
        return Response({
            'error': 'Only manufacturers can create batches'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Check if manufacturer is approved
    try:
        manufacturer = request.user.manufacturer_profile
        if manufacturer.approval_status != 'APPROVED':
            return Response({
                'error': 'Manufacturer must be approved before creating batches'
            }, status=status.HTTP_403_FORBIDDEN)
    except Manufacturer.DoesNotExist:
        return Response({
            'error': 'Manufacturer profile not found. Please register first.'
        }, status=status.HTTP_404_NOT_FOUND)
    
    serializer = BatchSerializer(data=request.data)
    if serializer.is_valid():
        # Verify that the product belongs to this manufacturer
        product_id = serializer.validated_data['product'].id
        try:
            product = Product.objects.get(id=product_id, manufacturer=manufacturer)
        except Product.DoesNotExist:
            return Response({
                'error': 'Product not found or does not belong to your manufacturer'
            }, status=status.HTTP_404_NOT_FOUND)
        
        batch = serializer.save()
        return Response({
            'message': 'Batch created successfully',
            'batch': BatchSerializer(batch).data
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def batch_list(request):
    """
    GET /batches
    List all batches (filtered by user role)
    """
    batches = Batch.objects.all()
    
    # Filter by manufacturer if user is a manufacturer
    if request.user.role == 'MANUFACTURER':
        try:
            manufacturer = request.user.manufacturer_profile
            batches = batches.filter(product__manufacturer=manufacturer)
        except Manufacturer.DoesNotExist:
            batches = Batch.objects.none()
    
    # Apply pagination
    page = request.query_params.get('page', 1)
    page_size = request.query_params.get('page_size', 20)
    
    try:
        page = int(page)
        page_size = int(page_size)
    except ValueError:
        page = 1
        page_size = 20
    
    start = (page - 1) * page_size
    end = start + page_size
    
    serializer = BatchSerializer(batches[start:end], many=True)
    return Response({
        'count': batches.count(),
        'page': page,
        'page_size': page_size,
        'results': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def batch_detail(request, id):
    """
    GET /batches/{id}
    Get batch details
    """
    try:
        batch = Batch.objects.get(id=id)
        
        # Check permissions
        if request.user.role == 'MANUFACTURER':
            try:
                manufacturer = request.user.manufacturer_profile
                if batch.product.manufacturer != manufacturer:
                    return Response({
                        'error': 'You do not have permission to view this batch'
                    }, status=status.HTTP_403_FORBIDDEN)
            except Manufacturer.DoesNotExist:
                return Response({
                    'error': 'Manufacturer profile not found'
                }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = BatchSerializer(batch)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Batch.DoesNotExist:
        return Response({
            'error': 'Batch not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def batch_generate_qr(request, batchId):
    """
    POST /batches/{batchId}/generate-qr
    Generate QR codes for a batch
    """
    # Check if user is a manufacturer
    if request.user.role != 'MANUFACTURER':
        return Response({
            'error': 'Only manufacturers can generate QR codes'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        batch = Batch.objects.get(id=batchId)
        
        # Verify ownership
        try:
            manufacturer = request.user.manufacturer_profile
            if batch.product.manufacturer != manufacturer:
                return Response({
                    'error': 'You do not have permission to generate QR codes for this batch'
                }, status=status.HTTP_403_FORBIDDEN)
        except Manufacturer.DoesNotExist:
            return Response({
                'error': 'Manufacturer profile not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get number of QR codes to generate (default 20)
        num_qr_codes = int(request.data.get('quantity', 20))
        
        if num_qr_codes <= 0 or num_qr_codes > 1000:
            return Response({
                'error': 'Quantity must be between 1 and 1000'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate QR codes
        qr_codes = []
        with transaction.atomic():
            for i in range(num_qr_codes):
                # Generate unique QR code value
                qr_value = f"PHARMA-{batch.product.product_code}-{batch.batch_number}-{secrets.token_hex(8).upper()}"
                
                qr_code = QRCode.objects.create(
                    batch=batch,
                    qr_code_value=qr_value,
                    is_active=True
                )
                qr_codes.append(qr_code)
        
        serializer = QRCodeSerializer(qr_codes, many=True)
        return Response({
            'message': f'{num_qr_codes} QR codes generated successfully',
            'batch_id': str(batch.id),
            'batch_number': batch.batch_number,
            'qr_codes': serializer.data
        }, status=status.HTTP_201_CREATED)
        
    except Batch.DoesNotExist:
        return Response({
            'error': 'Batch not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except ValueError:
        return Response({
            'error': 'Invalid quantity parameter'
        }, status=status.HTTP_400_BAD_REQUEST)


# ==================== QR VERIFICATION ====================

@api_view(['POST'])
@permission_classes([permissions.AllowAny])  # Public endpoint for QR scanning
def verify_qr(request):
    """
    POST /verify/qr
    Verify a QR code and log the scan
    """
    serializer = QRVerificationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    qr_code_value = serializer.validated_data['qr_code_value']
    scanned_by_role = serializer.validated_data['scanned_by_role']
    scan_location_city = serializer.validated_data['scan_location_city']
    scan_location_country = serializer.validated_data.get('scan_location_country', 'Pakistan')
    device_type = serializer.validated_data['device_type']
    
    # Step 1: Check if QR code exists in PostgreSQL
    try:
        qr_code = QRCode.objects.get(qr_code_value=qr_code_value, is_active=True)
        batch = qr_code.batch
    except QRCode.DoesNotExist:
        # Log invalid scan
        mongodb_client.log_scan(
            qr_code_value=qr_code_value,
            batch_id=None,
            scanned_by_role=scanned_by_role,
            scan_location_city=scan_location_city,
            scan_location_country=scan_location_country,
            verification_result='INVALID',
            device_type=device_type
        )
        return Response({
            'verification_result': 'INVALID',
            'message': 'QR code not found or inactive'
        }, status=status.HTTP_200_OK)
    
    # Step 2: Check if QR code has been scanned before (in MongoDB)
    has_been_scanned = mongodb_client.check_if_scanned(qr_code_value)
    
    # Step 3: Determine verification result
    if has_been_scanned:
        verification_result = 'ALREADY_SCANNED'
        message = 'This QR code has been scanned before. Product may be counterfeit or duplicate.'
    else:
        verification_result = 'GENUINE'
        message = 'QR code verified. Product is genuine.'
    
    # Step 4: Log the scan in MongoDB
    mongodb_client.log_scan(
        qr_code_value=qr_code_value,
        batch_id=batch.id,
        scanned_by_role=scanned_by_role,
        scan_location_city=scan_location_city,
        scan_location_country=scan_location_country,
        verification_result=verification_result,
        device_type=device_type
    )
    
    # Step 5: Return response
    response_data = {
        'verification_result': verification_result,
        'batch_id': str(batch.id),
        'batch_number': batch.batch_number,
        'product_name': batch.product.product_name,
        'manufacturing_date': batch.manufacturing_date,
        'expiry_date': batch.expiry_date,
        'message': message
    }
    
    return Response(response_data, status=status.HTTP_200_OK)
