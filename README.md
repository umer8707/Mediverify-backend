# Pharmaceutical Product Verification System - Backend

Blockchain-based pharmaceutical product verification system backend built with Django REST Framework.

## Tech Stack

- **Backend Framework**: Django 4.2.7 + Django REST Framework
- **Relational Database**: PostgreSQL (main system data)
- **NoSQL Database**: MongoDB (scan & verification logs)
- **Authentication**: JWT (Simple JWT)
- **Location Context**: Lahore, Punjab, Pakistan

## Project Structure

```
backend_fyp/
├── api/                          # Main application
│   ├── models.py                 # PostgreSQL models (User, Manufacturer, Product, Batch, QRCode)
│   ├── serializers.py            # DRF serializers
│   ├── views.py                  # API views
│   ├── urls.py                   # URL routing
│   ├── admin.py                  # Django admin configuration
│   ├── mongodb_client.py         # MongoDB connection and utilities
│   └── management/
│       └── commands/
│           └── seed_data.py      # Database seeder
├── pharma_verify/                # Django project settings
│   ├── settings.py               # Django configuration
│   └── urls.py                   # Main URL configuration
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment variables template
└── README.md                     # This file
```

## Database Models

### PostgreSQL Models

1. **User**: Custom user model with role-based access (ADMIN, MANUFACTURER, DISTRIBUTOR, PHARMACY, CONSUMER)
2. **Manufacturer**: Manufacturer profiles requiring admin approval
3. **Product**: Pharmaceutical products catalog
4. **Batch**: Manufacturing batches (most important model) with blockchain fields
5. **QRCode**: Unique QR codes linked to batches

### MongoDB Collections

- **scan_logs**: Stores all QR code scan events with location, device type, and verification results

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login and get JWT tokens

### Manufacturer
- `POST /api/manufacturers/register` - Register manufacturer profile (requires MANUFACTURER role)
- `POST /api/manufacturers/approve` - Approve/reject manufacturer (requires ADMIN role)

### Product
- `POST /api/products/create` - Create new product (requires approved MANUFACTURER)

### Batch
- `POST /api/batches/create` - Create new batch (requires approved MANUFACTURER)
- `GET /api/batches` - List batches (filtered by role)
- `GET /api/batches/{id}` - Get batch details
- `POST /api/batches/{batchId}/generate-qr` - Generate QR codes for a batch

### QR Verification
- `POST /api/verify/qr` - Verify QR code (public endpoint)

## Setup Instructions

### Prerequisites

- Python 3.8+
- PostgreSQL 12+
- MongoDB 4.4+
- pip (Python package manager)

### Step 1: Clone and Navigate

```bash
cd /home/saad/Desktop/backend_fyp
```

### Step 2: Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env` with your database credentials:

```env
SECRET_KEY=your-secret-key-here
DEBUG=True

DB_NAME=pharma_verify_db
DB_USER=postgres
DB_PASSWORD=your_postgres_password
DB_HOST=localhost
DB_PORT=5432

MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_DB=pharma_verify_logs
```

### Step 5: Setup PostgreSQL Database

```bash
# Login to PostgreSQL
sudo -u postgres psql

# Create database
CREATE DATABASE pharma_verify_db;

# Create user (if needed)
CREATE USER postgres WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE pharma_verify_db TO postgres;

# Exit PostgreSQL
\q
```

### Step 6: Setup MongoDB

```bash
# Start MongoDB service
sudo systemctl start mongod
# Or on macOS: brew services start mongodb-community

# MongoDB will use default settings (localhost:27017)
# No additional setup needed for development
```

### Step 7: Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 8: Create Superuser (Optional)

```bash
python manage.py createsuperuser
```

### Step 9: Seed Database with Dummy Data

```bash
python manage.py seed_data
```

This will create:
- 1 Admin user
- 2 Manufacturers (ABC Pharma, PakHealth Laboratories)
- 3 Products (Paracetamol, Amoxicillin, Cough Syrup)
- 6-9 Batches with manufacturing/expiry dates
- 120+ QR codes (20+ per batch)
- Sample scan logs in MongoDB

### Step 10: Run Development Server

```bash
python manage.py runserver
```

The API will be available at `http://localhost:8000/api/`

## Seeded Data

### Default Credentials

**Admin:**
- Email: `admin@pharmaverify.com`
- Password: `admin123`

**Manufacturers:**
- Email: `abcpharma@example.com` / Password: `manufacturer123`
- Email: `pakhealth@example.com` / Password: `manufacturer123`

### Sample Data

- **Manufacturers**: ABC Pharma Pvt Ltd (Kot Lakhpat), PakHealth Laboratories (Sundar Industrial Estate)
- **Products**: Paracetamol 500mg, Amoxicillin 250mg, Cough Syrup 120ml
- **Batches**: Manufacturing dates within last 6 months, expiry dates 1-2 years ahead
- **Distribution Regions**: Lahore, Faisalabad, Gujranwala
- **Scan Locations**: Lahore, DHA Phase 6, Gulberg, Johar Town

## API Usage Examples

### Register User

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password123",
    "full_name": "John Doe",
    "role": "CONSUMER",
    "phone_number": "+923001234567",
    "city": "Lahore",
    "country": "Pakistan"
  }'
```

### Login

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password123"
  }'
```

### Verify QR Code

```bash
curl -X POST http://localhost:8000/api/verify/qr \
  -H "Content-Type: application/json" \
  -d '{
    "qr_code_value": "PHARMA-ABC-PARA-500-BATCH-001-XXXXXXXX",
    "scanned_by_role": "CONSUMER",
    "scan_location_city": "Lahore",
    "scan_location_country": "Pakistan",
    "device_type": "ANDROID"
  }'
```

## QR Verification Logic

When `/api/verify/qr` is called:

1. **Check PostgreSQL**: Verify QR code exists and is active
2. **Check MongoDB**: Check if QR code has been scanned before
3. **Determine Result**:
   - `INVALID`: QR code not found
   - `ALREADY_SCANNED`: QR code scanned before (potential duplicate/counterfeit)
   - `GENUINE`: First-time scan, product is genuine
4. **Log Scan**: Record scan event in MongoDB with location, device, and timestamp

## Blockchain Integration (Future)

The system is prepared for blockchain integration:

- `Batch.blockchain_tx_hash`: Stores transaction hash when batch is registered
- `Batch.blockchain_status`: Tracks registration status (NOT_REGISTERED, PENDING, REGISTERED)

These fields are currently nullable and can be populated when blockchain integration is implemented.

## Development Notes

- **JWT Tokens**: Access tokens expire in 24 hours, refresh tokens in 7 days
- **CORS**: Configured for localhost:3000 (frontend) and localhost:8000
- **Pagination**: Batch list endpoint supports `page` and `page_size` query parameters
- **Role-Based Access**: All endpoints (except auth and verify) require authentication and appropriate roles

## Testing

To test the API endpoints, you can use:

- **Postman**: Import the endpoints and test with JWT tokens
- **curl**: Use the examples above
- **Django Admin**: Access at `http://localhost:8000/admin/`

## Troubleshooting

### Database Connection Issues

- Ensure PostgreSQL is running: `sudo systemctl status postgresql`
- Check database credentials in `.env`
- Verify database exists: `psql -U postgres -l`

### MongoDB Connection Issues

- Ensure MongoDB is running: `sudo systemctl status mongod`
- Check MongoDB connection: `mongosh` or `mongo`

### Migration Issues

- If migrations fail, try: `python manage.py migrate --run-syncdb`
- Reset migrations: Delete `api/migrations/` (except `__init__.py`) and re-run migrations

## Production Deployment

For production:

1. Set `DEBUG=False` in `.env`
2. Generate new `SECRET_KEY`
3. Configure proper CORS origins
4. Use environment-specific database credentials
5. Set up proper logging
6. Use production-grade WSGI server (Gunicorn, uWSGI)
7. Configure reverse proxy (Nginx)
8. Enable HTTPS

## License

This project is part of a Final Year Project (FYP).

