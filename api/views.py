"""
API Views for Pharmaceutical Product Verification System
"""

import secrets
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from django.db import transaction

from django.db import IntegrityError
from django.db.models import Sum, Q
from django.shortcuts import get_object_or_404
from .models import User, Manufacturer, Product, Batch, QRCode, Pharmacy, Distributor, BatchDispatch, DispensedQR
from .serializers import (
    UserSerializer, UserLoginSerializer, ManufacturerSerializer,
    ManufacturerApprovalSerializer, ProductSerializer, BatchSerializer,
    QRCodeSerializer, QRVerificationSerializer, QRVerificationResponseSerializer,
    PharmacySerializer, DistributorSerializer, BatchDispatchSerializer,
)
from .mongodb_client import mongodb_client
from .blockchain import register_batch_on_chain, verify_batch_on_chain

# ==================== API INDEX (GET /api/ shows this) ====================

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def api_root(request):
    """List available API endpoints. Visit http://127.0.0.1:8000/api/ to see this."""
    base = request.build_absolute_uri('/api/').rstrip('/')
    return Response({
        'message': 'Mediverify API. Use these URLs (POST/GET as noted).',
        'endpoints': {
            'auth_register': f'{base}/auth/register (POST)',
            'auth_login': f'{base}/auth/login (POST)',
            'manufacturers_register': f'{base}/manufacturers/register (POST)',
            'manufacturers_approve': f'{base}/manufacturers/approve (POST)',
            'products_create': f'{base}/products/create (POST)',
            'batches_list': f'{base}/batches (GET)',
            'batches_create': f'{base}/batches/create (POST)',
            'batches_detail': f'{base}/batches/<uuid> (GET)',
            'batches_generate_qr': f'{base}/batches/<batchId>/generate-qr (POST)',
            'verify_qr': f'{base}/verify/qr (POST)',
        },
        'admin': request.build_absolute_uri('/admin/'),
    })


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

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def manufacturer_profile(request):
    """
    GET /manufacturers/profile
    Return the logged-in manufacturer's own profile
    """
    if request.user.role != 'MANUFACTURER':
        return Response({'error': 'Only manufacturers can access this endpoint'}, status=status.HTTP_403_FORBIDDEN)
    try:
        manufacturer = request.user.manufacturer_profile
        return Response({
            'id': str(manufacturer.id),
            'company_name': manufacturer.company_name,
            'drug_license_number': manufacturer.drug_license_number,
            'city': manufacturer.city,
            'country': manufacturer.country,
            'manufacturing_address': manufacturer.manufacturing_address,
            'approval_status': manufacturer.approval_status,
            'created_at': manufacturer.created_at.isoformat(),
        }, status=status.HTTP_200_OK)
    except Manufacturer.DoesNotExist:
        return Response({'error': 'Manufacturer profile not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def manufacturer_list(request):
    """
    GET /manufacturers
    List all manufacturers (ADMIN only)
    """
    if request.user.role != 'ADMIN':
        return Response({
            'error': 'Only admins can view manufacturers'
        }, status=status.HTTP_403_FORBIDDEN)

    manufacturers = Manufacturer.objects.select_related('user').all()
    data = [
        {
            'id': str(manufacturer.id),
            'company_name': manufacturer.company_name,
            'drug_license_number': manufacturer.drug_license_number,
            'city': manufacturer.city,
            'country': manufacturer.country,
            'approval_status': manufacturer.approval_status,
            'approved_at': manufacturer.approved_at,
            'created_at': manufacturer.created_at,
            'email': manufacturer.user.email,
            'full_name': manufacturer.user.full_name,
            'is_active': manufacturer.user.is_active,
        }
        for manufacturer in manufacturers
    ]
    return Response(data, status=status.HTTP_200_OK)


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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def manufacturer_deactivate(request):
    """POST /manufacturers/deactivate — ADMIN only. Deactivate or reactivate a manufacturer."""
    if request.user.role != 'ADMIN':
        return Response({'error': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)
    manufacturer_id = request.data.get('manufacturer_id')
    action = request.data.get('action')
    if not manufacturer_id or action not in ['DEACTIVATE', 'REACTIVATE']:
        return Response({'error': 'manufacturer_id and action (DEACTIVATE/REACTIVATE) are required.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        manufacturer = Manufacturer.objects.select_related('user').get(id=manufacturer_id)
        manufacturer.user.is_active = (action == 'REACTIVATE')
        manufacturer.user.save(update_fields=['is_active'])
        verb = 'reactivated' if action == 'REACTIVATE' else 'deactivated'
        return Response({'message': f'Manufacturer {verb} successfully.'}, status=status.HTTP_200_OK)
    except Manufacturer.DoesNotExist:
        return Response({'error': 'Manufacturer not found.'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def manufacturer_detail(request, id):
    """GET /manufacturers/<id> — ADMIN only. Returns full manufacturer profile."""
    if request.user.role != 'ADMIN':
        return Response({'error': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)
    try:
        manufacturer = Manufacturer.objects.select_related('user').get(id=id)
        return Response(ManufacturerSerializer(manufacturer).data)
    except Manufacturer.DoesNotExist:
        return Response({'error': 'Manufacturer not found.'}, status=status.HTTP_404_NOT_FOUND)


# ==================== PRODUCT ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def product_list(request):
    """
    GET /products
    List products (ADMIN sees all, MANUFACTURER sees own products)
    """
    if request.user.role == 'MANUFACTURER':
        products = Product.objects.select_related('manufacturer').filter(
            manufacturer__user=request.user
        )
    elif request.user.role == 'ADMIN':
        manufacturer_id = request.query_params.get('manufacturer_id')
        if manufacturer_id:
            products = Product.objects.select_related('manufacturer').filter(manufacturer__id=manufacturer_id)
        else:
            products = Product.objects.select_related('manufacturer').all()
    else:
        products = Product.objects.none()

    data = [
        {
            'id': str(product.id),
            'name': product.product_name,
            'product_code': product.product_code,
            'description': product.description,
            'created_at': product.created_at,
            'manufacturer_name': product.manufacturer.company_name,
        }
        for product in products
    ]
    return Response(data, status=status.HTTP_200_OK)


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
        
        try:
            with transaction.atomic():
                batch = serializer.save()
                tx_hash = register_batch_on_chain(
                    batch_id=str(batch.id),
                    medicine_name=batch.product.product_name,
                    mfg_date=str(batch.manufacturing_date),
                    exp_date=str(batch.expiry_date),
                )
                batch.blockchain_tx_hash = tx_hash
                batch.blockchain_status = 'REGISTERED'
                batch.save(update_fields=['blockchain_tx_hash', 'blockchain_status'])
        except IntegrityError:
            return Response(
                {'error': 'Batch number already exists for this product.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception:
            return Response(
                {'error': 'Blockchain registration failed. Please check your connection and try again.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

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
    elif request.user.role == 'ADMIN':
        manufacturer_id = request.query_params.get('manufacturer_id')
        if manufacturer_id:
            batches = batches.filter(product__manufacturer__id=manufacturer_id)

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
    
    if request.user.role == 'MANUFACTURER':
        page_batches = list(batches.annotate(
            qty_dispatched=Sum(
                'dispatches__quantity',
                filter=Q(dispatches__dispatched_by=request.user)
            )
        )[start:end])
        serialized = BatchSerializer(page_batches, many=True).data
        results = [
            {**dict(b), 'quantity_dispatched': (page_batches[i].qty_dispatched or 0),
             'quantity_available': b['quantity_manufactured'] - (page_batches[i].qty_dispatched or 0)}
            for i, b in enumerate(serialized)
        ]
    else:
        results = BatchSerializer(batches[start:end], many=True).data

    return Response({
        'count': batches.count(),
        'page': page,
        'page_size': page_size,
        'results': results
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


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def batch_qr_codes(request, batchId):
    """
    GET /batches/{batchId}/qr-codes
    Retrieve existing QR codes for a batch
    """
    try:
        batch = Batch.objects.get(id=batchId)
        if request.user.role == 'MANUFACTURER':
            try:
                manufacturer = request.user.manufacturer_profile
                if batch.product.manufacturer != manufacturer:
                    return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
            except Manufacturer.DoesNotExist:
                return Response({'error': 'Manufacturer profile not found'}, status=status.HTTP_404_NOT_FOUND)
        qr_codes = QRCode.objects.filter(batch=batch, is_active=True).order_by('-created_at')
        serializer = QRCodeSerializer(qr_codes, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Batch.DoesNotExist:
        return Response({'error': 'Batch not found'}, status=status.HTTP_404_NOT_FOUND)


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

        # Block QR generation for fully dispatched or inactive batches
        if batch.batch_status in ('EXPIRED', 'RECALLED'):
            return Response({
                'error': f'Cannot generate QR codes for a {batch.batch_status.lower()} batch.'
            }, status=status.HTTP_400_BAD_REQUEST)
        if batch.expiry_date < timezone.now().date():
            return Response({
                'error': 'Cannot generate QR codes for an expired batch.'
            }, status=status.HTTP_400_BAD_REQUEST)
        qty_dispatched = BatchDispatch.objects.filter(
            batch=batch, dispatched_by=request.user
        ).aggregate(total=Sum('quantity'))['total'] or 0
        if qty_dispatched >= batch.quantity_manufactured:
            return Response({
                'error': 'Cannot generate QR codes: all units in this batch have been dispatched.'
            }, status=status.HTTP_400_BAD_REQUEST)

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


# ==================== BATCH DISPATCH / INVENTORY ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def batch_dispatch(request, id):
    """POST /batches/<id>/dispatch — MANUFACTURER or DISTRIBUTOR dispatches units to next tier."""
    if request.user.role not in ('MANUFACTURER', 'DISTRIBUTOR'):
        return Response({'error': 'Only manufacturers and distributors can dispatch.'}, status=status.HTTP_403_FORBIDDEN)
    batch = get_object_or_404(Batch, id=id)

    if request.user.role == 'MANUFACTURER':
        try:
            if batch.product.manufacturer.user != request.user:
                return Response({'error': 'This batch does not belong to you.'}, status=status.HTTP_403_FORBIDDEN)
        except Manufacturer.DoesNotExist:
            return Response({'error': 'Manufacturer profile not found.'}, status=status.HTTP_404_NOT_FOUND)

    dispatched_to_id = request.data.get('dispatched_to')
    try:
        quantity = int(request.data.get('quantity', 0))
    except (TypeError, ValueError):
        return Response({'error': 'Quantity must be a positive integer.'}, status=status.HTTP_400_BAD_REQUEST)
    notes = request.data.get('notes', '')

    if quantity <= 0:
        return Response({'error': 'Quantity must be positive.'}, status=status.HTTP_400_BAD_REQUEST)
    if not dispatched_to_id:
        return Response({'error': 'dispatched_to (user id) is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        recipient = User.objects.get(id=dispatched_to_id)
    except User.DoesNotExist:
        return Response({'error': 'Recipient user not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.user.role == 'MANUFACTURER' and recipient.role != 'DISTRIBUTOR':
        return Response({'error': 'Manufacturers can only dispatch to distributors.'}, status=status.HTTP_400_BAD_REQUEST)
    if request.user.role == 'DISTRIBUTOR' and recipient.role != 'PHARMACY':
        return Response({'error': 'Distributors can only dispatch to pharmacies.'}, status=status.HTTP_400_BAD_REQUEST)

    already_sent = BatchDispatch.objects.filter(batch=batch, dispatched_by=request.user).aggregate(Sum('quantity'))['quantity__sum'] or 0
    if request.user.role == 'MANUFACTURER':
        if already_sent + quantity > batch.quantity_manufactured:
            return Response({'error': f'Cannot dispatch more than quantity manufactured ({batch.quantity_manufactured}). Already dispatched: {already_sent}.'}, status=status.HTTP_400_BAD_REQUEST)
    else:
        received = BatchDispatch.objects.filter(batch=batch, dispatched_to=request.user).aggregate(Sum('quantity'))['quantity__sum'] or 0
        if already_sent + quantity > received:
            return Response({'error': f'Cannot dispatch more than received ({received - already_sent} units remaining).'}, status=status.HTTP_400_BAD_REQUEST)

    dispatch = BatchDispatch.objects.create(
        batch=batch, dispatched_by=request.user,
        dispatched_to=recipient, quantity=quantity, notes=notes
    )
    if request.user.role == 'MANUFACTURER' and batch.batch_status == 'CREATED':
        batch.batch_status = 'DISTRIBUTED'
        batch.save(update_fields=['batch_status'])

    return Response(BatchDispatchSerializer(dispatch).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def batch_dispatches(request, id):
    """GET /batches/<id>/dispatches — ADMIN or owning MANUFACTURER views dispatch chain."""
    batch = get_object_or_404(Batch, id=id)
    if request.user.role == 'ADMIN':
        dispatches = BatchDispatch.objects.filter(batch=batch).select_related('dispatched_by', 'dispatched_to', 'batch__product')
    elif request.user.role == 'MANUFACTURER':
        try:
            if batch.product.manufacturer.user != request.user:
                return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        except Manufacturer.DoesNotExist:
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        dispatches = BatchDispatch.objects.filter(batch=batch).select_related('dispatched_by', 'dispatched_to', 'batch__product')
    else:
        return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
    return Response(BatchDispatchSerializer(dispatches, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def batch_traceability(request, batch_id):
    """GET /batches/<id>/traceability — full supply chain journey for a batch (manufacturer or admin)."""
    batch = get_object_or_404(Batch, id=batch_id)

    if request.user.role == 'MANUFACTURER':
        try:
            if batch.product.manufacturer.user != request.user:
                return Response({'error': 'Not authorized.'}, status=status.HTTP_403_FORBIDDEN)
        except Exception:
            return Response({'error': 'Not authorized.'}, status=status.HTTP_403_FORBIDDEN)
    elif request.user.role != 'ADMIN':
        return Response({'error': 'Not authorized.'}, status=status.HTTP_403_FORBIDDEN)

    # Manufacturer → Distributor dispatches
    dist_dispatches = BatchDispatch.objects.filter(
        batch=batch,
        dispatched_by=batch.product.manufacturer.user
    ).select_related('dispatched_to').order_by('dispatched_at')

    distributor_data = []
    for d in dist_dispatches:
        # Distributor → Pharmacy dispatches for this batch
        pharm_dispatches = BatchDispatch.objects.filter(
            batch=batch,
            dispatched_by=d.dispatched_to
        ).select_related('dispatched_to').order_by('dispatched_at')

        pharmacy_data = []
        for p in pharm_dispatches:
            dispensed = DispensedQR.objects.filter(
                batch=batch, dispensed_by=p.dispatched_to
            ).count()
            try:
                pharmacy_name = p.dispatched_to.pharmacy.pharmacy_name
            except Exception:
                pharmacy_name = p.dispatched_to.full_name
            pharmacy_data.append({
                'pharmacy_name': pharmacy_name,
                'city': p.dispatched_to.city,
                'quantity_received': p.quantity,
                'quantity_dispensed': dispensed,
                'quantity_on_hand': p.quantity - dispensed,
                'dispatched_at': p.dispatched_at,
                'notes': p.notes or '',
            })

        qty_forwarded = sum(ph['quantity_received'] for ph in pharmacy_data)
        try:
            dist_name = d.dispatched_to.distributor.company_name
        except Exception:
            dist_name = d.dispatched_to.full_name

        distributor_data.append({
            'distributor_name': dist_name,
            'city': d.dispatched_to.city,
            'quantity_received': d.quantity,
            'quantity_forwarded': qty_forwarded,
            'quantity_on_hand': d.quantity - qty_forwarded,
            'dispatched_at': d.dispatched_at,
            'notes': d.notes or '',
            'pharmacies': pharmacy_data,
        })

    total_dispatched = sum(d['quantity_received'] for d in distributor_data)
    total_qr = QRCode.objects.filter(batch=batch).count()
    total_dispensed = DispensedQR.objects.filter(batch=batch).count()

    return Response({
        'batch_id': str(batch.id),
        'batch_number': batch.batch_number,
        'product_name': batch.product.product_name,
        'batch_status': batch.batch_status,
        'manufacturing_date': batch.manufacturing_date,
        'expiry_date': batch.expiry_date,
        'created_at': batch.created_at,
        'quantity_manufactured': batch.quantity_manufactured,
        'quantity_dispatched': total_dispatched,
        'quantity_available': batch.quantity_manufactured - total_dispatched,
        'manufacturer': {
            'name': batch.product.manufacturer.company_name,
            'city': batch.product.manufacturer.city,
        },
        'distributors': distributor_data,
        'qr_stats': {
            'total_generated': total_qr,
            'total_dispensed': total_dispensed,
        },
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def inventory(request):
    """GET /inventory — DISTRIBUTOR or PHARMACY views their current stock."""
    if request.user.role not in ('DISTRIBUTOR', 'PHARMACY'):
        return Response({'error': 'Only distributors and pharmacies can view inventory.'}, status=status.HTTP_403_FORBIDDEN)
    received_qs = BatchDispatch.objects.filter(dispatched_to=request.user).values('batch').annotate(quantity_received=Sum('quantity'))
    result = []
    for item in received_qs:
        try:
            batch = Batch.objects.select_related('product').get(id=item['batch'])
        except Batch.DoesNotExist:
            continue
        sent = 0
        if request.user.role == 'DISTRIBUTOR':
            sent = BatchDispatch.objects.filter(batch=batch, dispatched_by=request.user).aggregate(Sum('quantity'))['quantity__sum'] or 0
        elif request.user.role == 'PHARMACY':
            sent = DispensedQR.objects.filter(batch=batch, dispensed_by=request.user).count()
        result.append({
            'batch_id': str(batch.id),
            'batch_number': batch.batch_number,
            'product_name': batch.product.product_name,
            'expiry_date': batch.expiry_date,
            'batch_status': batch.batch_status,
            'quantity_received': item['quantity_received'],
            'quantity_sent': sent,
            'quantity_on_hand': item['quantity_received'] - sent,
        })
    return Response(result)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def batch_recall(request, id):
    """POST /batches/<id>/recall — MANUFACTURER recalls their own batch; ADMIN can recall any."""
    if request.user.role not in ('MANUFACTURER', 'ADMIN'):
        return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
    batch = get_object_or_404(Batch, id=id)
    if request.user.role == 'MANUFACTURER':
        try:
            if batch.product.manufacturer.user != request.user:
                return Response({'error': 'This batch does not belong to you.'}, status=status.HTTP_403_FORBIDDEN)
        except Manufacturer.DoesNotExist:
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
    batch.batch_status = 'RECALLED'
    batch.save(update_fields=['batch_status'])
    recipients = list(
        BatchDispatch.objects.filter(batch=batch)
        .select_related('dispatched_to')
        .values('dispatched_to__full_name', 'dispatched_to__email', 'dispatched_to__role')
        .distinct()
    )
    return Response({
        'message': f'Batch {batch.batch_number} recalled successfully.',
        'affected_recipients': recipients,
    })


# ==================== CHATBOT ====================

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def chatbot(request):
    """POST /chatbot — proxy to Groq Llama 3.3 70B. Open to all users (no login required)."""
    import requests as req_lib
    from decouple import config

    message = request.data.get('message', '').strip()
    history = request.data.get('history', [])
    if not message:
        return Response({'error': 'Message is required.'}, status=status.HTTP_400_BAD_REQUEST)

    user_role = request.user.role.title() if request.user.is_authenticated and hasattr(request.user, 'role') else 'Guest'

    system_prompt = (
        f"You are a medicine verification assistant for MediVerify, a pharmaceutical "
        f"authentication system used in Pakistan's drug supply chain. "
        f"The user is a {user_role}. "
        f"Help with: medicine verification, QR code scanning, counterfeit drug detection, "
        f"dosage information, storage conditions, expiry dates, drug interactions, and how "
        f"the MediVerify supply chain works (Manufacturer -> Distributor -> Pharmacy). "
        f"Keep answers concise and helpful. Redirect off-topic questions back to medicine."
    )

    context_lines = []
    try:
        if request.user.is_authenticated:
            if request.user.role == 'PHARMACY':
                recalled = list(Batch.objects.filter(
                    dispatches__dispatched_to=request.user,
                    batch_status='RECALLED'
                ).values_list('product__name', 'batch_number').distinct())
                if recalled:
                    context_lines.append(
                        "Recalled batches in this pharmacy's stock: " +
                        ", ".join(f"{n} (batch {b})" for n, b in recalled)
                    )
                else:
                    context_lines.append("This pharmacy has no recalled batches currently in stock.")

            elif request.user.role == 'DISTRIBUTOR':
                top = list(BatchDispatch.objects
                           .filter(dispatched_by=request.user)
                           .values('batch__product__name')
                           .annotate(total=Sum('quantity'))
                           .order_by('-total')[:5])
                if top:
                    context_lines.append(
                        "Distributor's top dispatched products: " +
                        ", ".join(t['batch__product__name'] for t in top)
                    )

            elif request.user.role == 'MANUFACTURER':
                products = list(Product.objects.filter(
                    manufacturer=request.user.manufacturer_profile
                ).values_list('name', flat=True))
                if products:
                    context_lines.append(
                        "Manufacturer's registered products: " + ", ".join(products)
                    )
        else:
            recalled = list(Batch.objects.filter(
                batch_status='RECALLED'
            ).values_list('product__name', 'batch_number')[:10])
            if recalled:
                context_lines.append(
                    "Currently recalled batches in the system: " +
                    ", ".join(f"{n} (batch {b})" for n, b in recalled)
                )
    except Exception:
        pass

    if context_lines:
        system_prompt += "\n\nReal-time context:\n" + "\n".join(context_lines)

    messages = [{'role': 'system', 'content': system_prompt}]
    for h in history[-10:]:
        if h.get('role') in ('user', 'assistant') and h.get('content'):
            messages.append({'role': h['role'], 'content': h['content']})
    messages.append({'role': 'user', 'content': message})

    try:
        groq_key = config('GROQ_API_KEY')
    except Exception as e:
        return Response({'error': f'GROQ_API_KEY not configured: {e}'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    try:
        resp = req_lib.post(
            'https://api.groq.com/openai/v1/chat/completions',
            json={
                'model': 'llama-3.3-70b-versatile',
                'messages': messages,
                'max_tokens': 800,
                'temperature': 0.7,
            },
            headers={'Authorization': f'Bearer {groq_key}'},
            timeout=30,
        )
        if not resp.ok:
            print(f'[chatbot] Groq error {resp.status_code}: {resp.text}')
            return Response({'error': f'Groq error {resp.status_code}: {resp.text}'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        reply = resp.json()['choices'][0]['message']['content']
        return Response({'reply': reply})
    except Exception as e:
        print(f'[chatbot] Unexpected error: {e}')
        return Response({'error': f'AI service error: {str(e)}'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


# ==================== QR VERIFICATION ====================

@csrf_exempt
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
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
        scanned_by_user_id = request.user.id if request.user.is_authenticated else None
        mongodb_client.log_scan(
            qr_code_value=qr_code_value,
            batch_id=None,
            scanned_by_role=scanned_by_role,
            scan_location_city=scan_location_city,
            scan_location_country=scan_location_country,
            verification_result='INVALID',
            device_type=device_type,
            scanned_by_user_id=scanned_by_user_id
        )
        return Response({
            'verification_result': 'INVALID',
            'message': 'QR code not found or inactive'
        }, status=status.HTTP_200_OK)
    
    # Step 2: Check if this role has already scanned this QR
    has_been_scanned = mongodb_client.check_if_scanned_by_role(qr_code_value, scanned_by_role)

    # Step 3: Determine verification result
    first_scan = None
    pharmacy_details = None
    if has_been_scanned:
        verification_result = 'ALREADY_SCANNED'
        message = 'This product has already been dispensed by a pharmacy.'
        first_scan = mongodb_client.get_first_scan_by_role(qr_code_value, scanned_by_role)
        try:
            dispense_record = DispensedQR.objects.select_related('dispensed_by').get(qr_code=qr_code)
            try:
                pharm_name = dispense_record.dispensed_by.pharmacy.pharmacy_name
            except Exception:
                pharm_name = dispense_record.dispensed_by.full_name
            pharmacy_details = {
                'pharmacy_name': pharm_name,
                'city': dispense_record.dispensed_by.city,
                'dispensed_at': dispense_record.dispensed_at.isoformat(),
            }
        except DispensedQR.DoesNotExist:
            pass
    else:
        verification_result = 'GENUINE'
        message = 'QR code verified. Product is genuine.'
        # Record a dispense event when a pharmacy scans a genuine QR for the first time
        if (request.user.is_authenticated
                and hasattr(request.user, 'role')
                and request.user.role == 'PHARMACY'):
            DispensedQR.objects.get_or_create(
                qr_code=qr_code,
                dispensed_by=request.user,
                defaults={'batch': batch}
            )

    # Step 4: Log the duplicate scan attempt in MongoDB (so it's recorded)
    scanned_by_user_id = request.user.id if request.user.is_authenticated else None
    mongodb_client.log_scan(
        qr_code_value=qr_code_value,
        batch_id=batch.id,
        scanned_by_role=scanned_by_role,
        scan_location_city=scan_location_city,
        scan_location_country=scan_location_country,
        verification_result=verification_result,
        device_type=device_type,
        scanned_by_user_id=scanned_by_user_id
    )

    # Step 5: Blockchain cross-check (non-blocking — None means couldn't reach chain)
    blockchain_verified = verify_batch_on_chain(str(batch.id))

    # Step 6: Return response
    response_data = {
        'verification_result': verification_result,
        'qr_code_value': qr_code_value,
        'batch_id': str(batch.id),
        'batch_number': batch.batch_number,
        'product_name': batch.product.product_name,
        'manufacturing_date': batch.manufacturing_date,
        'expiry_date': batch.expiry_date,
        'message': message,
        'first_scan': first_scan,
        'pharmacy_details': pharmacy_details,
        'blockchain_verified': blockchain_verified,
        'blockchain_status': batch.blockchain_status,
        'blockchain_tx_hash': batch.blockchain_tx_hash,
    }

    return Response(response_data, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def trace_qr(request):
    """
    GET /verify/qr/trace?qr=<qr_code_value>
    Returns the full supply chain traceability for a QR code.
    """
    qr_code_value = request.query_params.get('qr', '').strip()
    if not qr_code_value:
        return Response({'error': 'qr parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        qr_obj = QRCode.objects.select_related(
            'batch__product__manufacturer'
        ).get(qr_code_value=qr_code_value)
        batch = qr_obj.batch
        product = batch.product
        mfr = product.manufacturer
        product_info = {
            'product_name': product.product_name,
            'batch_number': batch.batch_number,
            'manufacturing_date': str(batch.manufacturing_date),
            'expiry_date': str(batch.expiry_date),
        }
        manufactured_stage = {
            'stage': 'Manufactured',
            'role': 'MANUFACTURER',
            'completed': True,
            'timestamp': batch.created_at.isoformat(),
            'location': f"{mfr.city}, {mfr.country}",
            'actor': mfr.company_name,
        }
    except QRCode.DoesNotExist:
        return Response({'error': 'QR code not found.'}, status=status.HTTP_404_NOT_FOUND)

    scan_events = mongodb_client.get_trace(qr_code_value)
    role_map = {e['scanned_by_role']: e for e in scan_events}

    stages = [manufactured_stage]
    for role, label in [('PHARMACY', 'Pharmacy Verified'), ('CONSUMER', 'Consumer Purchased')]:
        event = role_map.get(role)
        if event:
            city = event.get('scan_location_city', '')
            country = event.get('scan_location_country', '')
            location_parts = [p for p in [city, country] if p]
            location = ', '.join(location_parts) if location_parts else 'Unknown'
        else:
            location = None
        stages.append({
            'stage': label,
            'role': role,
            'completed': event is not None,
            'timestamp': event['scanned_at'] if event else None,
            'location': location,
            'actor': None,
        })

    # Determine status for each stage: completed / skipped / pending
    role_order = ['MANUFACTURER', 'PHARMACY', 'CONSUMER']
    completed_roles = {s['role'] for s in stages if s['completed']}
    for stage in stages:
        if stage['completed']:
            stage['status'] = 'completed'
        else:
            idx = role_order.index(stage['role'])
            later_completed = any(r in completed_roles for r in role_order[idx + 1:])
            stage['status'] = 'skipped' if later_completed else 'pending'

    # Suspicious if consumer scanned but pharmacy stage was skipped
    consumer_done = 'CONSUMER' in completed_roles
    skipped_stages = [s['stage'] for s in stages if s['status'] == 'skipped']
    suspicious = consumer_done and len(skipped_stages) > 0
    suspicious_reason = (
        f"Product reached consumer without passing through: {', '.join(skipped_stages)}."
        if suspicious else ''
    )

    return Response({
        **product_info,
        'qr_code_value': qr_code_value,
        'suspicious': suspicious,
        'suspicious_reason': suspicious_reason,
        'stages': stages,
    }, status=status.HTTP_200_OK)


# ==================== SCAN LOGS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def scan_logs(request):
    """
    GET /scan-logs
    ADMIN: all scan logs. MANUFACTURER: logs for their batches only.
    """
    limit = int(request.query_params.get('limit', 100))
    if request.user.role == 'ADMIN':
        manufacturer_id = request.query_params.get('manufacturer_id')
        if manufacturer_id:
            batch_ids = list(map(str, Batch.objects.filter(
                product__manufacturer__id=manufacturer_id
            ).values_list('id', flat=True)))
            logs = mongodb_client.get_scan_logs_by_batches(batch_ids, limit=limit)
        else:
            logs = mongodb_client.get_scan_logs(limit=limit)
    elif request.user.role == 'MANUFACTURER':
        batch_ids = list(map(str, Batch.objects.filter(
            product__manufacturer__user=request.user
        ).values_list('id', flat=True)))
        logs = mongodb_client.get_scan_logs_by_batches(batch_ids, limit=limit)
    elif request.user.role in ('PHARMACY', 'DISTRIBUTOR'):
        logs = mongodb_client.get_scan_logs_by_user(request.user.id, limit=limit)
    else:
        logs = []
    return Response(logs, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def counterfeit_alerts(request):
    """
    GET /counterfeit-alerts
    ADMIN: all alerts. MANUFACTURER: alerts for their batches only.
    """
    limit = int(request.query_params.get('limit', 100))
    if request.user.role == 'ADMIN':
        manufacturer_id = request.query_params.get('manufacturer_id')
        if manufacturer_id:
            batch_ids = list(map(str, Batch.objects.filter(
                product__manufacturer__id=manufacturer_id
            ).values_list('id', flat=True)))
            alerts = mongodb_client.get_counterfeit_alerts_by_batches(batch_ids, limit=limit)
        else:
            alerts = mongodb_client.get_counterfeit_alerts(limit=limit)
    elif request.user.role == 'MANUFACTURER':
        batch_ids = list(map(str, Batch.objects.filter(
            product__manufacturer__user=request.user
        ).values_list('id', flat=True)))
        alerts = mongodb_client.get_counterfeit_alerts_by_batches(batch_ids, limit=limit)
    else:
        alerts = []
    return Response(alerts, status=status.HTTP_200_OK)


# ==================== PHARMACY ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pharmacy_register(request):
    """POST /pharmacy/register"""
    if request.user.role != 'PHARMACY':
        return Response({'error': 'Only users with PHARMACY role can register a pharmacy.'}, status=status.HTTP_403_FORBIDDEN)
    if Pharmacy.objects.filter(user=request.user).exists():
        return Response({'error': 'Pharmacy profile already exists.'}, status=status.HTTP_400_BAD_REQUEST)
    required = ['pharmacy_name', 'license_number', 'city', 'country']
    for field in required:
        if not request.data.get(field):
            return Response({'error': f'{field} is required.'}, status=status.HTTP_400_BAD_REQUEST)
    if Pharmacy.objects.filter(license_number=request.data['license_number']).exists():
        return Response({'error': 'A pharmacy with this license number already exists.'}, status=status.HTTP_400_BAD_REQUEST)
    pharmacy = Pharmacy.objects.create(
        user=request.user,
        pharmacy_name=request.data['pharmacy_name'],
        license_number=request.data['license_number'],
        city=request.data['city'],
        country=request.data['country'],
    )
    return Response({'message': 'Pharmacy registration submitted. Awaiting admin approval.', 'pharmacy': PharmacySerializer(pharmacy).data}, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pharmacy_profile(request):
    """GET /pharmacy/profile"""
    if request.user.role != 'PHARMACY':
        return Response({'error': 'Only pharmacy users can access this endpoint.'}, status=status.HTTP_403_FORBIDDEN)
    try:
        pharmacy = request.user.pharmacy_profile
        return Response(PharmacySerializer(pharmacy).data, status=status.HTTP_200_OK)
    except Pharmacy.DoesNotExist:
        return Response({'error': 'Pharmacy profile not found. Please register first.'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pharmacy_list(request):
    """GET /pharmacies — ADMIN sees all; MANUFACTURER and DISTRIBUTOR see approved only (for dispatch)."""
    if request.user.role == 'ADMIN':
        pharmacies = Pharmacy.objects.select_related('user').all()
    elif request.user.role in ('MANUFACTURER', 'DISTRIBUTOR'):
        pharmacies = Pharmacy.objects.select_related('user').filter(approval_status='APPROVED')
    else:
        return Response({'error': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)
    return Response(PharmacySerializer(pharmacies, many=True).data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pharmacy_approve(request):
    """POST /pharmacy/approve — ADMIN only"""
    if request.user.role != 'ADMIN':
        return Response({'error': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)
    pharmacy_id = request.data.get('pharmacy_id')
    approval_status = request.data.get('approval_status')
    if not pharmacy_id or approval_status not in ['APPROVED', 'REJECTED']:
        return Response({'error': 'pharmacy_id and approval_status (APPROVED/REJECTED) are required.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        pharmacy = Pharmacy.objects.get(id=pharmacy_id)
        pharmacy.approval_status = approval_status
        pharmacy.approved_by = request.user
        pharmacy.approved_at = timezone.now()
        pharmacy.save()
        return Response({'message': f'Pharmacy {approval_status.lower()} successfully.'}, status=status.HTTP_200_OK)
    except Pharmacy.DoesNotExist:
        return Response({'error': 'Pharmacy not found.'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pharmacy_deactivate(request):
    """POST /pharmacy/deactivate — ADMIN only. Deactivate or reactivate a pharmacy."""
    if request.user.role != 'ADMIN':
        return Response({'error': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)
    pharmacy_id = request.data.get('pharmacy_id')
    action = request.data.get('action')
    if not pharmacy_id or action not in ['DEACTIVATE', 'REACTIVATE']:
        return Response({'error': 'pharmacy_id and action (DEACTIVATE/REACTIVATE) are required.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        pharmacy = Pharmacy.objects.select_related('user').get(id=pharmacy_id)
        pharmacy.user.is_active = (action == 'REACTIVATE')
        pharmacy.user.save(update_fields=['is_active'])
        verb = 'reactivated' if action == 'REACTIVATE' else 'deactivated'
        return Response({'message': f'Pharmacy {verb} successfully.'}, status=status.HTTP_200_OK)
    except Pharmacy.DoesNotExist:
        return Response({'error': 'Pharmacy not found.'}, status=status.HTTP_404_NOT_FOUND)


# ==================== DISTRIBUTOR ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def distributor_register(request):
    """POST /distributor/register"""
    if request.user.role != 'DISTRIBUTOR':
        return Response({'error': 'Only users with DISTRIBUTOR role can register a distributor.'}, status=status.HTTP_403_FORBIDDEN)
    if Distributor.objects.filter(user=request.user).exists():
        return Response({'error': 'Distributor profile already exists.'}, status=status.HTTP_400_BAD_REQUEST)
    required = ['company_name', 'license_number', 'city', 'country']
    for field in required:
        if not request.data.get(field):
            return Response({'error': f'{field} is required.'}, status=status.HTTP_400_BAD_REQUEST)
    if Distributor.objects.filter(license_number=request.data['license_number']).exists():
        return Response({'error': 'A distributor with this license number already exists.'}, status=status.HTTP_400_BAD_REQUEST)
    distributor = Distributor.objects.create(
        user=request.user,
        company_name=request.data['company_name'],
        license_number=request.data['license_number'],
        city=request.data['city'],
        country=request.data['country'],
    )
    return Response({'message': 'Distributor registration submitted. Awaiting admin approval.', 'distributor': DistributorSerializer(distributor).data}, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def distributor_profile(request):
    """GET /distributor/profile"""
    if request.user.role != 'DISTRIBUTOR':
        return Response({'error': 'Only distributor users can access this endpoint.'}, status=status.HTTP_403_FORBIDDEN)
    try:
        distributor = request.user.distributor_profile
        return Response(DistributorSerializer(distributor).data, status=status.HTTP_200_OK)
    except Distributor.DoesNotExist:
        return Response({'error': 'Distributor profile not found. Please register first.'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def distributor_list(request):
    """GET /distributors — ADMIN sees all; MANUFACTURER sees approved only (for dispatch)."""
    if request.user.role == 'ADMIN':
        distributors = Distributor.objects.select_related('user').all()
    elif request.user.role == 'MANUFACTURER':
        distributors = Distributor.objects.select_related('user').filter(approval_status='APPROVED')
    else:
        return Response({'error': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)
    return Response(DistributorSerializer(distributors, many=True).data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def distributor_approve(request):
    """POST /distributor/approve — ADMIN only"""
    if request.user.role != 'ADMIN':
        return Response({'error': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)
    distributor_id = request.data.get('distributor_id')
    approval_status = request.data.get('approval_status')
    if not distributor_id or approval_status not in ['APPROVED', 'REJECTED']:
        return Response({'error': 'distributor_id and approval_status (APPROVED/REJECTED) are required.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        distributor = Distributor.objects.get(id=distributor_id)
        distributor.approval_status = approval_status
        distributor.approved_by = request.user
        distributor.approved_at = timezone.now()
        distributor.save()
        return Response({'message': f'Distributor {approval_status.lower()} successfully.'}, status=status.HTTP_200_OK)
    except Distributor.DoesNotExist:
        return Response({'error': 'Distributor not found.'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def distributor_deactivate(request):
    """POST /distributor/deactivate — ADMIN only. Deactivate or reactivate a distributor."""
    if request.user.role != 'ADMIN':
        return Response({'error': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)
    distributor_id = request.data.get('distributor_id')
    action = request.data.get('action')
    if not distributor_id or action not in ['DEACTIVATE', 'REACTIVATE']:
        return Response({'error': 'distributor_id and action (DEACTIVATE/REACTIVATE) are required.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        distributor = Distributor.objects.select_related('user').get(id=distributor_id)
        distributor.user.is_active = (action == 'REACTIVATE')
        distributor.user.save(update_fields=['is_active'])
        verb = 'reactivated' if action == 'REACTIVATE' else 'deactivated'
        return Response({'message': f'Distributor {verb} successfully.'}, status=status.HTTP_200_OK)
    except Distributor.DoesNotExist:
        return Response({'error': 'Distributor not found.'}, status=status.HTTP_404_NOT_FOUND)

