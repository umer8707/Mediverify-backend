# Quick Setup Guide

## Prerequisites Check

Before starting, ensure you have:

1. **Python 3.8+** installed
   ```bash
   python3 --version
   ```

2. **PostgreSQL** installed and running
   ```bash
   sudo systemctl status postgresql
   # If not installed: sudo apt-get install postgresql postgresql-contrib
   ```

3. **MongoDB** installed and running
   ```bash
   sudo systemctl status mongod
   # If not installed: sudo apt-get install mongodb
   ```

## Quick Start

### 1. Create Virtual Environment

```bash
cd /home/saad/Desktop/backend_fyp
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Setup PostgreSQL

```bash
# Login as postgres user
sudo -u postgres psql

# In PostgreSQL shell:
CREATE DATABASE pharma_verify_db;
# If you need to create a user:
CREATE USER postgres WITH PASSWORD 'postgres';
GRANT ALL PRIVILEGES ON DATABASE pharma_verify_db TO postgres;
\q
```

### 4. Configure Environment

Create `.env` file:

```bash
cat > .env << EOF
SECRET_KEY=django-insecure-dev-key-change-in-production
DEBUG=True
DB_NAME=pharma_verify_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_DB=pharma_verify_logs
MONGODB_USER=
MONGODB_PASSWORD=
EOF
```

### 5. Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Seed Database

```bash
python manage.py seed_data
```

### 7. Run Server

```bash
python manage.py runserver
```

## Verify Setup

### Test API Endpoints

1. **Register a user:**
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "test123",
    "full_name": "Test User",
    "role": "CONSUMER",
    "phone_number": "+923001234567",
    "city": "Lahore",
    "country": "Pakistan"
  }'
```

2. **Login:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "test123"
  }'
```

3. **Get a QR code from database and verify:**
```bash
# First, get a QR code (you can check Django admin or database)
# Then verify it:
curl -X POST http://localhost:8000/api/verify/qr \
  -H "Content-Type: application/json" \
  -d '{
    "qr_code_value": "PHARMA-ABC-PARA-500-BATCH-ABC-PARA-500-001-XXXXXXXX",
    "scanned_by_role": "CONSUMER",
    "scan_location_city": "Lahore",
    "scan_location_country": "Pakistan",
    "device_type": "ANDROID"
  }'
```

## Default Credentials (After Seeding)

- **Admin**: `admin@pharmaverify.com` / `admin123`
- **Manufacturer 1**: `abcpharma@example.com` / `manufacturer123`
- **Manufacturer 2**: `pakhealth@example.com` / `manufacturer123`

## Troubleshooting

### PostgreSQL Connection Error

```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Check if database exists
sudo -u postgres psql -l

# Test connection
psql -U postgres -d pharma_verify_db
```

### MongoDB Connection Error

```bash
# Check if MongoDB is running
sudo systemctl status mongod

# Test MongoDB connection
mongosh
# Or: mongo
```

### Migration Errors

```bash
# Reset migrations (CAUTION: This will delete all data)
rm -rf api/migrations/0*.py
python manage.py makemigrations
python manage.py migrate
```

### Port Already in Use

```bash
# Use a different port
python manage.py runserver 8001
```

## Next Steps

1. Access Django Admin at `http://localhost:8000/admin/`
2. Test all API endpoints using Postman or curl
3. Integrate with frontend applications
4. Prepare for blockchain integration

