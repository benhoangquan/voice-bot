"""Guardrails and safety mechanisms"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import re


class Guardrails:
    """Multi-layer guardrails for safety and abuse prevention"""
    
    def __init__(self):
        self.rate_limits: Dict[str, List[datetime]] = defaultdict(list)
        self.failed_attempts: Dict[str, int] = defaultdict(int)
        self.blocked_calls: set = set()
        
        # Rate limiting config
        self.max_calls_per_hour = 10
        self.max_failed_attempts = 5
        self.block_duration = timedelta(hours=1)
        
        # Profanity filter (basic)
        self.profanity_patterns = [
            r'\b(shit|damn|hell|fuck|asshole)\b',
            # Add more patterns as needed
        ]
    
    def check_rate_limit(self, caller_id: str) -> bool:
        """Check if caller has exceeded rate limit"""
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        
        # Clean old entries
        self.rate_limits[caller_id] = [
            ts for ts in self.rate_limits[caller_id] if ts > hour_ago
        ]
        
        # Check limit
        if len(self.rate_limits[caller_id]) >= self.max_calls_per_hour:
            return False
        
        # Record this call
        self.rate_limits[caller_id].append(now)
        return True
    
    def check_blocked(self, caller_id: str) -> bool:
        """Check if caller is blocked"""
        return caller_id in self.blocked_calls
    
    def block_caller(self, caller_id: str):
        """Block a caller"""
        self.blocked_calls.add(caller_id)
    
    def check_profanity(self, text: str) -> bool:
        """Check if text contains profanity"""
        text_lower = text.lower()
        for pattern in self.profanity_patterns:
            if re.search(pattern, text_lower):
                return True
        return False
    
    def validate_reservation_info(self, info: Dict) -> tuple[bool, Optional[str]]:
        """Validate reservation information"""
        errors = []
        
        # Check required fields
        required_fields = ["date", "time", "party_size", "customer_phone"]
        for field in required_fields:
            if field not in info or not info[field]:
                errors.append(f"Missing required field: {field}")
        
        # Validate party size
        if "party_size" in info:
            try:
                party_size = int(info["party_size"])
                if party_size < 1 or party_size > 20:
                    errors.append("Party size must be between 1 and 20")
            except (ValueError, TypeError):
                errors.append("Party size must be a valid number")
        
        # Validate date format
        if "date" in info and info["date"]:
            try:
                datetime.strptime(info["date"], "%Y-%m-%d")
            except ValueError:
                errors.append("Date must be in YYYY-MM-DD format")
        
        # Validate time format
        if "time" in info and info["time"]:
            try:
                datetime.strptime(info["time"], "%H:%M")
            except ValueError:
                errors.append("Time must be in HH:MM format")
        
        # Validate phone number (basic)
        if "customer_phone" in info and info["customer_phone"]:
            phone = re.sub(r'\D', '', info["customer_phone"])
            if len(phone) < 10:
                errors.append("Invalid phone number format")
        
        if errors:
            return False, "; ".join(errors)
        
        return True, None
    
    def record_failed_attempt(self, caller_id: str):
        """Record a failed attempt"""
        self.failed_attempts[caller_id] += 1
        
        if self.failed_attempts[caller_id] >= self.max_failed_attempts:
            self.block_caller(caller_id)
            return True  # Blocked
        return False
    
    def reset_failed_attempts(self, caller_id: str):
        """Reset failed attempts for caller"""
        self.failed_attempts[caller_id] = 0
    
    def check_intent(self, text: str) -> str:
        """Classify intent (basic implementation)"""
        text_lower = text.lower()
        
        # Reservation keywords
        reservation_keywords = ["reservation", "book", "table", "reserve", "appointment"]
        if any(keyword in text_lower for keyword in reservation_keywords):
            return "reservation"
        
        # Menu keywords
        menu_keywords = ["menu", "food", "dish", "item", "price", "what do you have"]
        if any(keyword in text_lower for keyword in menu_keywords):
            return "menu_query"
        
        # Transfer keywords
        transfer_keywords = ["speak to", "human", "person", "manager", "help"]
        if any(keyword in text_lower for keyword in transfer_keywords):
            return "transfer"
        
        return "general"
