"""Base adapter interfaces using ABC pattern"""

from abc import ABC, abstractmethod
from typing import Dict, Any

class CalendarAdapter(ABC):
    """Base interface for calendar/reservation providers"""
    
    @abstractmethod
    async def create_reservation(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """Create a reservation"""
        pass
    
    @abstractmethod
    async def check_availability(self, date: str, time: str, party_size: int) -> bool:
        """Check if time slot is available"""
        pass
    
    @abstractmethod
    async def cancel_reservation(self, reservation_id: str) -> bool:
        """Cancel a reservation"""
        pass
