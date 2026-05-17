# Run Backend Locally & See Functionality (No Frontend Needed)

You **do not** need to add any APIs. The backend already has all endpoints. You can run it and test everything locally before connecting any frontend.

---

## 1. Run the backend

```powershell
cd e:\Mediverify-backend
.\venv\Scripts\Activate.ps1
python manage.py runserver
```

When you see **"Starting development server at http://127.0.0.1:8000/"**, the backend is running.

---

## 2. Two ways to see functionality (no frontend)

### Option A: Django Admin (easiest – use your browser)

1. Open: **http://127.0.0.1:8000/admin/**
2. Log in with seeded user. Django admin asks for **Username** and **Password**:
   - **Username:** type the **email** `admin@pharmaverify.com` (this project uses email as username)
   - **Password:** `admin123`
3. You can browse and edit: Users, Manufacturers, Products, Batches, QR codes.

This shows you that the backend and database are working.

---

### Option B: Call the APIs (Postman, curl, or browser)

- **Important:** Use **exact** URLs. Do **not** type `api/...` in the browser — that was only a placeholder in the docs. Real URLs have no dots.
- **See all endpoints in one place:** open **http://127.0.0.1:8000/api/** in your browser. You get a JSON list of every API URL.
- Base URL for all APIs: **http://127.0.0.1:8000/api/**

| What you want to do        | Method | URL | Auth? |
|----------------------------|--------|-----|-------|
| Register a user            | POST   | `/api/auth/register` | No |
| Login (get JWT)            | POST   | `/api/auth/login` | No |
| Register manufacturer      | POST   | `/api/manufacturers/register` | Yes (JWT) |
| Approve manufacturer       | POST   | `/api/manufacturers/approve` | Yes (Admin) |
| Create product             | POST   | `/api/products/create` | Yes (Manufacturer) |
| List batches               | GET    | `/api/batches` | Yes |
| Create batch               | POST   | `/api/batches/create` | Yes |
| Batch detail               | GET    | `/api/batches/{id}` | Yes |
| Generate QR for batch      | POST   | `/api/batches/{batchId}/generate-qr` | Yes |
| **Verify QR (scan)**       | POST   | `/api/verify/qr` | **No** (public) |

**Example – Login (get token):**

```http
POST http://127.0.0.1:8000/api/auth/login
Content-Type: application/json

{
  "email": "admin@pharmaverify.com",
  "password": "admin123"
}
```

Response includes `access` and `refresh` tokens. Use the **access** token in the header for protected endpoints:

```http
Authorization: Bearer <paste_access_token_here>
```

**Example – Verify a QR code (no auth):**

```http
POST http://127.0.0.1:8000/api/verify/qr
Content-Type: application/json

{
  "qr_code_value": "PHARMA-ABC-PARA-500-BATCH-001-XXXXXXXX",
  "scanned_by_role": "CONSUMER",
  "scan_location_city": "Lahore",
  "scan_location_country": "Pakistan",
  "device_type": "ANDROID"
}
```

(Use a real `qr_code_value` from Admin → QR codes, or from the seeded data.)

---

## 3. .env – what to set and where

Location: **`e:\Mediverify-backend\.env`** (root of the backend project).

### For “just run locally” (SQLite, no Postgres/Mongo)

You only need these; the rest can stay as-is or be left default:

| Variable      | What it is | Example / note |
|---------------|------------|----------------|
| `USE_SQLITE`  | Use SQLite so you don’t need PostgreSQL | `True` |
| `SECRET_KEY`  | Django secret (keep default for local) | `django-insecure-dev-key-change-in-production` |
| `DEBUG`       | Show errors in browser | `True` |

### When you add PostgreSQL later

| Variable     | What to put |
|-------------|-------------|
| `DB_NAME`   | Database name, e.g. `pharma_verify_db` |
| `DB_USER`   | PostgreSQL username |
| `DB_PASSWORD` | PostgreSQL password |
| `DB_HOST`   | Usually `localhost` |
| `DB_PORT`   | Usually `5432` |

Then set **`USE_SQLITE=False`** (or remove it) so the app uses Postgres.

### When you add MongoDB (optional – for scan logs)

| Variable        | What to put |
|-----------------|-------------|
| `MONGODB_HOST`  | Usually `localhost` |
| `MONGODB_PORT`  | Usually `27017` |
| `MONGODB_DB`    | e.g. `pharma_verify_logs` |
| `MONGODB_USER`  | Leave empty if no auth |
| `MONGODB_PASSWORD` | Leave empty if no auth |

### When you connect a frontend / deploy

| Variable        | What to put |
|-----------------|-------------|
| `ALLOWED_HOSTS` | If you set it in code/settings: your frontend or server host, e.g. `localhost:3000` or your domain |
| CORS is already set in the project for typical frontend URLs. |

### Blockchain (future)

| Variable           | What to put |
|--------------------|-------------|
| `SEPOLIA_RPC_URL`  | Ethereum Sepolia RPC URL (e.g. from Alchemy/Infura) |
| `CONTRACT_ADDRESS` | Your smart contract address on Sepolia |

---

## Summary

- **No APIs to add** – everything is already implemented. Run the server and use Admin or the API URLs above.
- **Run locally:** `python manage.py runserver` and open **http://127.0.0.1:8000/admin/** or call **http://127.0.0.1:8000/api/...**.
- **.env:** For local run, `USE_SQLITE=True`, `DEBUG=True`, and `SECRET_KEY` are enough. Fill DB/Mongo/blockchain variables when you add those services or the frontend.
