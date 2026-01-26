"""Queue-based staff transfer system"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import asyncio
from collections import deque


class TransferPriority(Enum):
    """Transfer priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class StaffStatus(Enum):
    """Staff availability status"""
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"


@dataclass
class TransferRequest:
    """Transfer request data structure"""
    call_sid: str
    caller_id: str
    reason: str
    context: Dict[str, Any]
    priority: TransferPriority = TransferPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    estimated_wait: Optional[int] = None  # seconds


@dataclass
class StaffMember:
    """Staff member data structure"""
    id: str
    name: str
    phone: str
    status: StaffStatus = StaffStatus.OFFLINE
    current_call: Optional[str] = None


class TransferQueue:
    """Queue-based staff transfer system"""
    
    def __init__(self):
        self.queue: deque = deque()
        self.staff: Dict[str, StaffMember] = {}
        self.active_transfers: Dict[str, TransferRequest] = {}
        self.lock = asyncio.Lock()
    
    def add_staff(self, staff: StaffMember):
        """Add staff member to the system"""
        self.staff[staff.id] = staff
    
    def update_staff_status(self, staff_id: str, status: StaffStatus, call_sid: Optional[str] = None):
        """Update staff member status"""
        if staff_id in self.staff:
            self.staff[staff_id].status = status
            self.staff[staff_id].current_call = call_sid
    
    async def enqueue_transfer(self, request: TransferRequest) -> int:
        """Add transfer request to queue"""
        async with self.lock:
            # Calculate position in queue
            position = len(self.queue) + 1
            
            # Insert based on priority
            inserted = False
            for i, existing in enumerate(self.queue):
                if request.priority.value > existing.priority.value:
                    self.queue.insert(i, request)
                    inserted = True
                    break
            
            if not inserted:
                self.queue.append(request)
            
            # Calculate estimated wait time
            available_staff = [s for s in self.staff.values() if s.status == StaffStatus.AVAILABLE]
            if available_staff:
                request.estimated_wait = 0
            else:
                # Estimate based on queue position and average call duration
                request.estimated_wait = position * 60  # 1 minute per position
            
            return position
    
    async def dequeue_transfer(self) -> Optional[TransferRequest]:
        """Get next transfer request from queue"""
        async with self.lock:
            if not self.queue:
                return None
            
            request = self.queue.popleft()
            self.active_transfers[request.call_sid] = request
            return request
    
    def get_available_staff(self) -> List[StaffMember]:
        """Get list of available staff members"""
        return [s for s in self.staff.values() if s.status == StaffStatus.AVAILABLE]
    
    async def assign_transfer(self, request: TransferRequest) -> Optional[StaffMember]:
        """Assign transfer to available staff"""
        available_staff = self.get_available_staff()
        
        if not available_staff:
            return None
        
        # Select first available staff (could implement round-robin or skill-based)
        staff = available_staff[0]
        self.update_staff_status(staff.id, StaffStatus.BUSY, request.call_sid)
        
        return staff
    
    def complete_transfer(self, call_sid: str):
        """Mark transfer as complete"""
        if call_sid in self.active_transfers:
            request = self.active_transfers[call_sid]
            
            # Find staff member and mark as available
            for staff in self.staff.values():
                if staff.current_call == call_sid:
                    self.update_staff_status(staff.id, StaffStatus.AVAILABLE, None)
                    break
            
            del self.active_transfers[call_sid]
    
    def get_queue_position(self, call_sid: str) -> Optional[int]:
        """Get position in queue for a call"""
        for i, request in enumerate(self.queue):
            if request.call_sid == call_sid:
                return i + 1
        return None
    
    def get_queue_length(self) -> int:
        """Get current queue length"""
        return len(self.queue)
