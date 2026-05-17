"""
PostgreSQL Models for Pharmaceutical Product Verification System
"""

import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.core.validators import RegexValidator


class UserManager(BaseUserManager):
    """Custom user manager"""
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'ADMIN')
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser):
    """
    Custom User model with role-based access control
    Roles: ADMIN, MANUFACTURER, DISTRIBUTOR, PHARMACY, CONSUMER
    """
    ROLE_CHOICES = [
        ('ADMIN', 'Admin'),
        ('MANUFACTURER', 'Manufacturer'),
        ('DISTRIBUTOR', 'Distributor'),
        ('PHARMACY', 'Pharmacy'),
        ('CONSUMER', 'Consumer'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    # password field is inherited from AbstractBaseUser
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    phone_number = models.CharField(
        max_length=20,
        validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")]
    )
    city = models.CharField(max_length=100, default='Lahore')
    country = models.CharField(max_length=100, default='Pakistan')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # Django admin access
    is_superuser = models.BooleanField(default=False)  # Django admin full access
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name', 'role']
    
    class Meta:
        db_table = 'users'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.full_name} ({self.email})"
    
    def has_perm(self, perm, obj=None):
        return self.is_superuser
    
    def has_module_perms(self, app_label):
        return self.is_superuser


class Manufacturer(models.Model):
    """
    Manufacturer profile linked to User
    Requires approval from ADMIN before activation
    """
    APPROVAL_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='manufacturer_profile')
    company_name = models.CharField(max_length=255)
    drug_license_number = models.CharField(max_length=100, unique=True)
    manufacturing_address = models.TextField()
    city = models.CharField(max_length=100, default='Lahore')
    country = models.CharField(max_length=100, default='Pakistan')
    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, default='PENDING')
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_manufacturers'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'manufacturers'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.company_name} ({self.drug_license_number})"


class Product(models.Model):
    """
    Pharmaceutical product catalog
    Each product belongs to a manufacturer
    """
    DOSAGE_FORM_CHOICES = [
        ('Tablet', 'Tablet'),
        ('Capsule', 'Capsule'),
        ('Syrup', 'Syrup'),
        ('Injection', 'Injection'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    manufacturer = models.ForeignKey(Manufacturer, on_delete=models.CASCADE, related_name='products')
    product_name = models.CharField(max_length=255)
    product_code = models.CharField(max_length=100, unique=True)
    dosage_form = models.CharField(max_length=50, choices=DOSAGE_FORM_CHOICES)
    strength = models.CharField(max_length=50)  # e.g., "500mg", "250mg"
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'products'
        ordering = ['product_name']
    
    def __str__(self):
        return f"{self.product_name} ({self.product_code})"


class Batch(models.Model):
    """
    Batch model - MOST IMPORTANT model in the system
    Represents a manufacturing batch of a product
    Includes blockchain fields for future integration
    """
    BATCH_STATUS_CHOICES = [
        ('CREATED', 'Created'),
        ('DISTRIBUTED', 'Distributed'),
        ('EXPIRED', 'Expired'),
        ('RECALLED', 'Recalled'),
    ]
    
    UNIT_TYPE_CHOICES = [
        ('Box', 'Box'),
        ('Bottle', 'Bottle'),
        ('Strip', 'Strip'),
    ]
    
    BLOCKCHAIN_STATUS_CHOICES = [
        ('NOT_REGISTERED', 'Not Registered'),
        ('PENDING', 'Pending'),
        ('REGISTERED', 'Registered'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='batches')
    batch_number = models.CharField(max_length=100)
    manufacturing_date = models.DateField()
    expiry_date = models.DateField()
    quantity_manufactured = models.PositiveIntegerField()
    unit_type = models.CharField(max_length=20, choices=UNIT_TYPE_CHOICES)
    manufacturing_site = models.CharField(max_length=255)
    quality_certification_code = models.CharField(max_length=100)
    storage_conditions = models.TextField()
    mrp_price = models.DecimalField(max_digits=10, decimal_places=2)
    distribution_region = models.CharField(max_length=255)
    batch_status = models.CharField(max_length=20, choices=BATCH_STATUS_CHOICES, default='CREATED')
    
    # Blockchain fields - Placeholders for future integration
    # NOTE: Blockchain integration is intentionally deferred. These fields are
    # kept as placeholders to maintain database schema compatibility for future
    # blockchain implementation. No blockchain write or read operations are
    # performed in the current codebase.
    blockchain_tx_hash = models.CharField(max_length=255, null=True, blank=True)
    blockchain_status = models.CharField(
        max_length=20,
        choices=BLOCKCHAIN_STATUS_CHOICES,
        default='NOT_REGISTERED'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'batches'
        unique_together = [['product', 'batch_number']]  # Unique batch number per product
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.product.product_name} - Batch {self.batch_number}"


class QRCode(models.Model):
    """
    QR Code model linked to a Batch
    Each QR code is unique and can be scanned for verification
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name='qr_codes')
    qr_code_value = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'qr_codes'
        ordering = ['-created_at']

    def __str__(self):
        return f"QR: {self.qr_code_value[:20]}... (Batch: {self.batch.batch_number})"


APPROVAL_STATUS_CHOICES = [
    ('PENDING', 'Pending'),
    ('APPROVED', 'Approved'),
    ('REJECTED', 'Rejected'),
]


class Pharmacy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='pharmacy_profile')
    pharmacy_name = models.CharField(max_length=255)
    license_number = models.CharField(max_length=100, unique=True)
    city = models.CharField(max_length=100, default='Lahore')
    country = models.CharField(max_length=100, default='Pakistan')
    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, default='PENDING')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_pharmacies')
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'pharmacies'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.pharmacy_name} ({self.license_number})"


class Distributor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='distributor_profile')
    company_name = models.CharField(max_length=255)
    license_number = models.CharField(max_length=100, unique=True)
    city = models.CharField(max_length=100, default='Lahore')
    country = models.CharField(max_length=100, default='Pakistan')
    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, default='PENDING')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_distributors')
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'distributors'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.company_name} ({self.license_number})"


class BatchDispatch(models.Model):
    """
    Records stock movement between supply chain participants.
    MANUFACTURER → DISTRIBUTOR
    DISTRIBUTOR → PHARMACY
    """
    batch         = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name='dispatches')
    dispatched_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dispatches_sent')
    dispatched_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dispatches_received')
    quantity      = models.PositiveIntegerField()
    notes         = models.TextField(blank=True)
    dispatched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'batch_dispatches'
        ordering = ['-dispatched_at']

    def __str__(self):
        return f"{self.batch.batch_number}: {self.quantity} units → {self.dispatched_to.full_name}"


class DispensedQR(models.Model):
    """
    Records each unique QR code dispensed by a pharmacy to a consumer.
    Created on the first GENUINE scan by an authenticated pharmacy user.
    unique_together prevents double-counting if the endpoint is called twice.
    """
    qr_code      = models.ForeignKey(QRCode, on_delete=models.CASCADE, related_name='dispense_records')
    dispensed_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dispensed_qrs')
    batch        = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name='dispenses')
    dispensed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'dispensed_qrs'
        unique_together = [('qr_code', 'dispensed_by')]
        ordering = ['-dispensed_at']

    def __str__(self):
        return f"{self.qr_code.qr_code_value[:20]}... dispensed by {self.dispensed_by.full_name}"
