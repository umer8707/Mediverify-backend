"""
MongoDB Client for storing scan and verification logs
"""

from pymongo import MongoClient
from django.conf import settings
from datetime import datetime


class MongoDBClient:
    """
    Singleton MongoDB client for scan logs.
    If MongoDB is unavailable, operations no-op so the app still runs (e.g. SQLite-only dev).
    """
    _instance = None
    _client = None
    _db = None
    _available = True  # False after connection failure
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MongoDBClient, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        pass  # Lazy connect on first use
    
    def _ensure_client(self):
        """Connect to MongoDB on first use. Sets _available=False if connection fails."""
        if not self._available or self._client is not None:
            return
        try:
            mongodb_config = settings.MONGODB_SETTINGS
            if mongodb_config.get('username') and mongodb_config.get('password'):
                connection_string = (
                    f"mongodb://{mongodb_config['username']}:{mongodb_config['password']}"
                    f"@{mongodb_config['host']}:{mongodb_config['port']}/{mongodb_config['db']}"
                )
            else:
                connection_string = f"mongodb://{mongodb_config['host']}:{mongodb_config['port']}/"
            self._client = MongoClient(connection_string, serverSelectionTimeoutMS=2000)
            self._db = self._client[mongodb_config['db']]
            # Verify connection
            self._client.server_info()
        except Exception:
            self._available = False
            self._client = None
            self._db = None
    
    @property
    def db(self):
        self._ensure_client()
        return self._db
    
    def get_scan_logs_collection(self):
        """Get the scan_logs collection, or None if MongoDB unavailable."""
        self._ensure_client()
        if self._db is None:
            return None
        return self._db.scan_logs
    
    def log_scan(self, qr_code_value, batch_id, scanned_by_role, scan_location_city,
                 scan_location_country, verification_result, device_type, scanned_by_user_id=None):
        """
        Log a QR code scan event to MongoDB. No-op if MongoDB unavailable.
        """
        try:
            collection = self.get_scan_logs_collection()
            if collection is None:
                return None
            log_entry = {
                'qr_code_value': qr_code_value,
                'batch_id': str(batch_id),
                'scanned_by_role': scanned_by_role,
                'scanned_by_user_id': str(scanned_by_user_id) if scanned_by_user_id else None,
                'scan_location_city': scan_location_city,
                'scan_location_country': scan_location_country,
                'scanned_at': datetime.utcnow(),
                'verification_result': verification_result,
                'device_type': device_type,
            }
            return collection.insert_one(log_entry).inserted_id
        except Exception:
            return None
    
    def check_if_scanned(self, qr_code_value):
        """Check if a QR code has been scanned before by any role."""
        try:
            collection = self.get_scan_logs_collection()
            if collection is None:
                return False
            return collection.count_documents({'qr_code_value': qr_code_value}) > 0
        except Exception:
            return False

    def check_if_scanned_by_role(self, qr_code_value, role):
        """
        Check if a QR code has already been scanned by this specific role.
        Each role (DISTRIBUTOR, PHARMACY, CONSUMER) is allowed exactly one scan.
        """
        try:
            collection = self.get_scan_logs_collection()
            if collection is None:
                return False
            return collection.count_documents({
                'qr_code_value': qr_code_value,
                'scanned_by_role': role,
            }) > 0
        except Exception:
            return False

    def get_first_scan_by_role(self, qr_code_value, role):
        """
        Return the earliest scan for this QR+role combination.
        Used to show original scan details when a duplicate is detected.
        """
        try:
            collection = self.get_scan_logs_collection()
            if collection is None:
                return None
            doc = collection.find_one(
                {'qr_code_value': qr_code_value, 'scanned_by_role': role},
                sort=[('scanned_at', 1)]
            )
            if not doc:
                return None
            return {
                'scanned_at': str(doc.get('scanned_at', '')),
                'scan_location_city': doc.get('scan_location_city', ''),
                'scan_location_country': doc.get('scan_location_country', ''),
            }
        except Exception:
            return None

    def get_trace(self, qr_code_value):
        """
        Return all scan events for a QR code sorted by time ascending (oldest first).
        Used to build the supply chain traceability timeline.
        """
        try:
            collection = self.get_scan_logs_collection()
            if collection is None:
                return []
            docs = list(collection.find(
                {'qr_code_value': qr_code_value},
                {'scanned_by_role': 1, 'scan_location_city': 1,
                 'scan_location_country': 1, 'scanned_at': 1, 'verification_result': 1}
            ).sort('scanned_at', 1))
            return [{
                'scanned_by_role': doc.get('scanned_by_role', ''),
                'scan_location_city': doc.get('scan_location_city', ''),
                'scan_location_country': doc.get('scan_location_country', ''),
                'scanned_at': str(doc.get('scanned_at', '')),
                'verification_result': doc.get('verification_result', ''),
            } for doc in docs]
        except Exception:
            return []
    
    def get_scan_logs(self, limit=100):
        """
        Return most recent scan log documents sorted by scanned_at descending.
        Returns [] if MongoDB unavailable.
        """
        try:
            collection = self.get_scan_logs_collection()
            if collection is None:
                return []
            docs = list(collection.find(
                {},
                {'qr_code_value': 1, 'batch_id': 1, 'scanned_by_role': 1,
                 'scan_location_city': 1, 'scan_location_country': 1,
                 'verification_result': 1, 'device_type': 1, 'scanned_at': 1}
            ).sort('scanned_at', -1).limit(limit))
            result = []
            for doc in docs:
                result.append({
                    'qr_code_value': doc.get('qr_code_value', ''),
                    'batch_id': doc.get('batch_id', ''),
                    'scanned_by_role': doc.get('scanned_by_role', ''),
                    'scan_location_city': doc.get('scan_location_city', ''),
                    'scan_location_country': doc.get('scan_location_country', ''),
                    'verification_result': doc.get('verification_result', ''),
                    'device_type': doc.get('device_type', ''),
                    'scanned_at': str(doc.get('scanned_at', '')),
                })
            return result
        except Exception:
            return []

    def get_counterfeit_alerts(self, limit=100):
        """
        Return scan log documents where verification_result is ALREADY_SCANNED.
        Returns [] if MongoDB unavailable.
        """
        try:
            collection = self.get_scan_logs_collection()
            if collection is None:
                return []
            docs = list(collection.find(
                {'verification_result': 'INVALID'},
                {'qr_code_value': 1, 'batch_id': 1, 'scanned_by_role': 1,
                 'scan_location_city': 1, 'scan_location_country': 1,
                 'verification_result': 1, 'device_type': 1, 'scanned_at': 1}
            ).sort('scanned_at', -1).limit(limit))
            result = []
            for doc in docs:
                result.append({
                    'qr_code_value': doc.get('qr_code_value', ''),
                    'batch_id': doc.get('batch_id', ''),
                    'scanned_by_role': doc.get('scanned_by_role', ''),
                    'scan_location_city': doc.get('scan_location_city', ''),
                    'scan_location_country': doc.get('scan_location_country', ''),
                    'verification_result': doc.get('verification_result', ''),
                    'device_type': doc.get('device_type', ''),
                    'scanned_at': str(doc.get('scanned_at', '')),
                })
            return result
        except Exception:
            return []

    def get_scan_logs_by_batches(self, batch_ids, limit=100):
        """
        Return scan logs for the given batch_ids sorted by scanned_at descending.
        Returns [] if MongoDB unavailable or batch_ids is empty.
        """
        if not batch_ids:
            return []
        try:
            collection = self.get_scan_logs_collection()
            if collection is None:
                return []
            docs = list(collection.find(
                {'batch_id': {'$in': batch_ids}},
                {'qr_code_value': 1, 'batch_id': 1, 'scanned_by_role': 1,
                 'scan_location_city': 1, 'scan_location_country': 1,
                 'verification_result': 1, 'device_type': 1, 'scanned_at': 1}
            ).sort('scanned_at', -1).limit(limit))
            return [{
                'qr_code_value': doc.get('qr_code_value', ''),
                'batch_id': doc.get('batch_id', ''),
                'scanned_by_role': doc.get('scanned_by_role', ''),
                'scan_location_city': doc.get('scan_location_city', ''),
                'scan_location_country': doc.get('scan_location_country', ''),
                'verification_result': doc.get('verification_result', ''),
                'device_type': doc.get('device_type', ''),
                'scanned_at': str(doc.get('scanned_at', '')),
            } for doc in docs]
        except Exception:
            return []

    def get_scan_logs_by_user(self, user_id, limit=100):
        """
        Return scan logs for a specific user (pharmacy/distributor) sorted by scanned_at descending.
        """
        if not user_id:
            return []
        try:
            collection = self.get_scan_logs_collection()
            if collection is None:
                return []
            docs = list(collection.find(
                {'scanned_by_user_id': str(user_id)},
                {'qr_code_value': 1, 'batch_id': 1, 'scanned_by_role': 1,
                 'scan_location_city': 1, 'scan_location_country': 1,
                 'verification_result': 1, 'device_type': 1, 'scanned_at': 1}
            ).sort('scanned_at', -1).limit(limit))
            return [{
                'qr_code_value': doc.get('qr_code_value', ''),
                'batch_id': doc.get('batch_id', ''),
                'scanned_by_role': doc.get('scanned_by_role', ''),
                'scan_location_city': doc.get('scan_location_city', ''),
                'scan_location_country': doc.get('scan_location_country', ''),
                'verification_result': doc.get('verification_result', ''),
                'device_type': doc.get('device_type', ''),
                'scanned_at': str(doc.get('scanned_at', '')),
            } for doc in docs]
        except Exception:
            return []

    def get_counterfeit_alerts_by_batches(self, batch_ids, limit=100):
        """
        Return ALREADY_SCANNED scan logs for the given batch_ids sorted by scanned_at descending.
        Returns [] if MongoDB unavailable or batch_ids is empty.
        """
        if not batch_ids:
            return []
        try:
            collection = self.get_scan_logs_collection()
            if collection is None:
                return []
            docs = list(collection.find(
                {'batch_id': {'$in': batch_ids}, 'verification_result': 'INVALID'},
                {'qr_code_value': 1, 'batch_id': 1, 'scanned_by_role': 1,
                 'scan_location_city': 1, 'scan_location_country': 1,
                 'verification_result': 1, 'device_type': 1, 'scanned_at': 1}
            ).sort('scanned_at', -1).limit(limit))
            return [{
                'qr_code_value': doc.get('qr_code_value', ''),
                'batch_id': doc.get('batch_id', ''),
                'scanned_by_role': doc.get('scanned_by_role', ''),
                'scan_location_city': doc.get('scan_location_city', ''),
                'scan_location_country': doc.get('scan_location_country', ''),
                'verification_result': doc.get('verification_result', ''),
                'device_type': doc.get('device_type', ''),
                'scanned_at': str(doc.get('scanned_at', '')),
            } for doc in docs]
        except Exception:
            return []

    def get_scan_history(self, qr_code_value, limit=10):
        """
        Get scan history for a QR code. Returns [] if MongoDB unavailable.
        """
        try:
            collection = self.get_scan_logs_collection()
            if collection is None:
                return []
            return list(collection.find(
                {'qr_code_value': qr_code_value}
            ).sort('scanned_at', -1).limit(limit))
        except Exception:
            return []


# Global instance
mongodb_client = MongoDBClient()

