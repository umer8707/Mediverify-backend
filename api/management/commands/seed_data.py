"""
Database seeder for pharmaceutical verification system
Seeds realistic Lahore, Pakistan-based dummy data
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import secrets
from api.models import User, Manufacturer, Product, Batch, QRCode
from api.mongodb_client import mongodb_client


class Command(BaseCommand):
    help = 'Seed database with realistic Lahore-based pharmaceutical data'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting database seeding...'))
        
        # Clear existing data (optional - comment out if you want to keep existing data)
        # self.clear_data()
        
        # Create data
        admin_user = self.create_admin()
        manufacturers = self.create_manufacturers()
        products = self.create_products(manufacturers)
        batches = self.create_batches(products)
        self.create_qr_codes(batches)
        self.create_sample_scan_logs()
        
        self.stdout.write(self.style.SUCCESS('Database seeding completed successfully!'))

    def clear_data(self):
        """Clear existing data (use with caution)"""
        self.stdout.write(self.style.WARNING('Clearing existing data...'))
        QRCode.objects.all().delete()
        Batch.objects.all().delete()
        Product.objects.all().delete()
        Manufacturer.objects.all().delete()
        User.objects.filter(role__in=['MANUFACTURER', 'DISTRIBUTOR', 'PHARMACY', 'CONSUMER']).delete()

    def create_admin(self):
        """Create admin user"""
        admin, created = User.objects.get_or_create(
            email='admin@pharmaverify.com',
            defaults={
                'full_name': 'System Administrator',
                'role': 'ADMIN',
                'phone_number': '+923001234567',
                'city': 'Lahore',
                'country': 'Pakistan',
                'is_active': True,
            }
        )
        if created:
            admin.set_password('admin123')
            admin.save()
            self.stdout.write(self.style.SUCCESS(f'Created admin user: {admin.email}'))
        else:
            self.stdout.write(self.style.WARNING(f'Admin user already exists: {admin.email}'))
        return admin

    def create_manufacturers(self):
        """Create manufacturer users and profiles"""
        manufacturers_data = [
            {
                'user': {
                    'email': 'abcpharma@example.com',
                    'full_name': 'Ahmed Ali',
                    'phone_number': '+923001111111',
                },
                'profile': {
                    'company_name': 'ABC Pharma Pvt Ltd',
                    'drug_license_number': 'DL-LHR-2023-001',
                    'manufacturing_address': 'Plot 45, Industrial Area, Kot Lakhpat, Lahore',
                    'city': 'Lahore',
                    'country': 'Pakistan',
                    'approval_status': 'APPROVED',
                }
            },
            {
                'user': {
                    'email': 'pakhealth@example.com',
                    'full_name': 'Fatima Khan',
                    'phone_number': '+923002222222',
                },
                'profile': {
                    'company_name': 'PakHealth Laboratories',
                    'drug_license_number': 'DL-LHR-2023-002',
                    'manufacturing_address': 'Block C, Sundar Industrial Estate, Lahore',
                    'city': 'Lahore',
                    'country': 'Pakistan',
                    'approval_status': 'APPROVED',
                }
            },
        ]
        
        manufacturers = []
        admin = User.objects.filter(role='ADMIN').first()
        
        for data in manufacturers_data:
            user, created = User.objects.get_or_create(
                email=data['user']['email'],
                defaults={
                    'full_name': data['user']['full_name'],
                    'role': 'MANUFACTURER',
                    'phone_number': data['user']['phone_number'],
                    'city': 'Lahore',
                    'country': 'Pakistan',
                    'is_active': True,
                }
            )
            if created:
                user.set_password('manufacturer123')
                user.save()
                self.stdout.write(self.style.SUCCESS(f'Created manufacturer user: {user.email}'))
            
            manufacturer, created = Manufacturer.objects.get_or_create(
                user=user,
                defaults={
                    **data['profile'],
                    'approved_by': admin,
                    'approved_at': timezone.now() if data['profile']['approval_status'] == 'APPROVED' else None,
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created manufacturer: {manufacturer.company_name}'))
            manufacturers.append(manufacturer)
        
        return manufacturers

    def create_products(self, manufacturers):
        """Create products for manufacturers"""
        products_data = [
            {
                'manufacturer': manufacturers[0],  # ABC Pharma
                'product_name': 'Paracetamol 500mg Tablets',
                'product_code': 'ABC-PARA-500',
                'dosage_form': 'Tablet',
                'strength': '500mg',
                'description': 'Paracetamol 500mg tablets for pain relief and fever reduction. Each tablet contains 500mg of paracetamol.',
            },
            {
                'manufacturer': manufacturers[0],  # ABC Pharma
                'product_name': 'Amoxicillin 250mg Capsules',
                'product_code': 'ABC-AMOX-250',
                'dosage_form': 'Capsule',
                'strength': '250mg',
                'description': 'Amoxicillin 250mg capsules, antibiotic for bacterial infections. Each capsule contains 250mg of amoxicillin trihydrate.',
            },
            {
                'manufacturer': manufacturers[1],  # PakHealth
                'product_name': 'Cough Syrup 120ml',
                'product_code': 'PKH-COUGH-120',
                'dosage_form': 'Syrup',
                'strength': '120ml',
                'description': 'Herbal cough syrup for dry and wet cough. Contains natural ingredients. Bottle size: 120ml.',
            },
        ]
        
        products = []
        for data in products_data:
            product, created = Product.objects.get_or_create(
                product_code=data['product_code'],
                defaults=data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created product: {product.product_name}'))
            products.append(product)
        
        return products

    def create_batches(self, products):
        """Create batches for products"""
        batches_data = []
        
        # Generate batches for each product
        for product in products:
            # Create 2-3 batches per product
            num_batches = 2 if product.product_code.startswith('PKH') else 3
            
            for i in range(num_batches):
                # Manufacturing date: within last 6 months
                manufacturing_date = timezone.now().date() - timedelta(days=30 * (6 - i * 2))
                
                # Expiry date: 1-2 years from manufacturing date
                expiry_date = manufacturing_date + timedelta(days=365 + (i * 90))
                
                # Distribution regions
                regions = ['Lahore', 'Faisalabad', 'Gujranwala']
                
                batch_data = {
                    'product': product,
                    'batch_number': f'BATCH-{product.product_code}-{i+1:03d}',
                    'manufacturing_date': manufacturing_date,
                    'expiry_date': expiry_date,
                    'quantity_manufactured': 10000 + (i * 10000),  # 10k, 20k, 30k
                    'unit_type': 'Box' if product.dosage_form in ['Tablet', 'Capsule'] else 'Bottle',
                    'manufacturing_site': product.manufacturer.manufacturing_address,
                    'quality_certification_code': f'QC-{product.product_code}-{manufacturing_date.strftime("%Y%m%d")}',
                    'storage_conditions': 'Store in a cool, dry place below 30°C. Keep away from direct sunlight.',
                    'mrp_price': 150.00 + (i * 25.00),
                    'distribution_region': regions[i % len(regions)],
                    'batch_status': 'DISTRIBUTED' if i > 0 else 'CREATED',
                    'blockchain_status': 'NOT_REGISTERED',
                }
                batches_data.append(batch_data)
        
        batches = []
        for data in batches_data:
            batch, created = Batch.objects.get_or_create(
                product=data['product'],
                batch_number=data['batch_number'],
                defaults=data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created batch: {batch.batch_number}'))
            batches.append(batch)
        
        return batches

    def create_qr_codes(self, batches):
        """Create QR codes for batches (at least 20 per batch)"""
        total_qr_codes = 0
        
        for batch in batches:
            # Generate 20-25 QR codes per batch
            num_qr_codes = 20 + (hash(str(batch.id)) % 6)  # Random between 20-25
            
            existing_count = QRCode.objects.filter(batch=batch).count()
            if existing_count >= 20:
                self.stdout.write(self.style.WARNING(f'Batch {batch.batch_number} already has {existing_count} QR codes'))
                continue
            
            qr_codes_to_create = num_qr_codes - existing_count
            
            for i in range(qr_codes_to_create):
                qr_value = f"PHARMA-{batch.product.product_code}-{batch.batch_number}-{secrets.token_hex(8).upper()}"
                
                qr_code, created = QRCode.objects.get_or_create(
                    qr_code_value=qr_value,
                    defaults={
                        'batch': batch,
                        'is_active': True,
                    }
                )
                if created:
                    total_qr_codes += 1
            
            self.stdout.write(self.style.SUCCESS(f'Created {qr_codes_to_create} QR codes for batch {batch.batch_number}'))
        
        self.stdout.write(self.style.SUCCESS(f'Total QR codes created: {total_qr_codes}'))

    def create_sample_scan_logs(self):
        """Create sample scan logs in MongoDB"""
        # Get some QR codes
        qr_codes = QRCode.objects.filter(is_active=True)[:10]
        
        if not qr_codes.exists():
            self.stdout.write(self.style.WARNING('No QR codes found to create scan logs'))
            return
        
        cities = ['Lahore', 'DHA Phase 6', 'Gulberg', 'Johar Town']
        roles = ['CONSUMER', 'PHARMACY', 'CONSUMER', 'CONSUMER']
        device_types = ['ANDROID', 'IOS', 'WEB', 'ANDROID']
        
        scan_count = 0
        for i, qr_code in enumerate(qr_codes):
            # Create 1-3 scans per QR code
            num_scans = (i % 3) + 1
            
            for j in range(num_scans):
                scan_time = timezone.now() - timedelta(days=j, hours=j*2)
                
                # First scan is GENUINE, subsequent are ALREADY_SCANNED
                verification_result = 'GENUINE' if j == 0 else 'ALREADY_SCANNED'
                
                mongodb_client.log_scan(
                    qr_code_value=qr_code.qr_code_value,
                    batch_id=qr_code.batch.id,
                    scanned_by_role=roles[i % len(roles)],
                    scan_location_city=cities[i % len(cities)],
                    scan_location_country='Pakistan',
                    verification_result=verification_result,
                    device_type=device_types[i % len(device_types)]
                )
                scan_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'Created {scan_count} sample scan logs in MongoDB'))

