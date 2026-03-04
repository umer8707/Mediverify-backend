"""
MongoDB Client for storing scan and verification logs
"""

from pymongo import MongoClient
from django.conf import settings
from datetime import datetime


class MongoDBClient:
    """
    Singleton MongoDB client for scan logs
    """
    _instance = None
    _client = None
    _db = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MongoDBClient, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            mongodb_config = settings.MONGODB_SETTINGS
            
            # Build connection string
            if mongodb_config.get('username') and mongodb_config.get('password'):
                connection_string = (
                    f"mongodb://{mongodb_config['username']}:{mongodb_config['password']}"
                    f"@{mongodb_config['host']}:{mongodb_config['port']}/{mongodb_config['db']}"
                )
            else:
                connection_string = f"mongodb://{mongodb_config['host']}:{mongodb_config['port']}/"
            
            self._client = MongoClient(connection_string)
            self._db = self._client[mongodb_config['db']]
    
    @property
    def db(self):
        return self._db
    
    def get_scan_logs_collection(self):
        """Get the scan_logs collection"""
        return self._db.scan_logs
    
    def log_scan(self, qr_code_value, batch_id, scanned_by_role, scan_location_city, 
                 scan_location_country, verification_result, device_type):
        """
        Log a QR code scan event to MongoDB
        
        Args:
            qr_code_value: The scanned QR code value
            batch_id: UUID of the batch
            scanned_by_role: Role of the person scanning (CONSUMER, PHARMACY, etc.)
            scan_location_city: City where scan occurred
            scan_location_country: Country where scan occurred
            verification_result: Result of verification (GENUINE, ALREADY_SCANNED, etc.)
            device_type: Device type (WEB, ANDROID, IOS)
        
        Returns:
            Inserted document ID
        """
        collection = self.get_scan_logs_collection()
        
        log_entry = {
            'qr_code_value': qr_code_value,
            'batch_id': str(batch_id),
            'scanned_by_role': scanned_by_role,
            'scan_location_city': scan_location_city,
            'scan_location_country': scan_location_country,
            'scan_timestamp': datetime.utcnow(),
            'verification_result': verification_result,
            'device_type': device_type,
        }
        
        return collection.insert_one(log_entry).inserted_id
    
    def check_if_scanned(self, qr_code_value):
        """
        Check if a QR code has been scanned before
        
        Args:
            qr_code_value: The QR code value to check
        
        Returns:
            True if scanned before, False otherwise
        """
        collection = self.get_scan_logs_collection()
        count = collection.count_documents({'qr_code_value': qr_code_value})
        return count > 0
    
    def get_scan_history(self, qr_code_value, limit=10):
        """
        Get scan history for a QR code
        
        Args:
            qr_code_value: The QR code value
            limit: Maximum number of records to return
        
        Returns:
            List of scan log documents
        """
        collection = self.get_scan_logs_collection()
        return list(collection.find(
            {'qr_code_value': qr_code_value}
        ).sort('scan_timestamp', -1).limit(limit))


# Global instance
mongodb_client = MongoDBClient()

