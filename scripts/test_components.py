"""Test script for various components"""

import sys
import os
import asyncio

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rag.menu_rag import MenuRAG, create_sample_menu_data
from src.guardrails.safety import Guardrails
from src.transfer.queue import TransferQueue, StaffMember, StaffStatus, TransferRequest, TransferPriority
from src.config import Config


async def test_menu_rag():
    """Test menu RAG system"""
    print("Testing Menu RAG...")
    
    # Create sample data if needed
    if not os.path.exists(Config.MENU_DATA_PATH):
        create_sample_menu_data(Config.MENU_DATA_PATH)
    
    menu_rag = MenuRAG(Config.CHROMA_DB_PATH)
    menu_rag.load_from_file(Config.MENU_DATA_PATH)
    
    # Test queries
    queries = [
        "What vegetarian options do you have?",
        "What's the price of salmon?",
        "Do you have gluten-free dishes?",
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        results = menu_rag.query(query, n_results=2)
        for result in results:
            print(f"  - {result['name']}: ${result['price']:.2f}")
    
    print("\n✓ Menu RAG test passed")


def test_guardrails():
    """Test guardrails"""
    print("\nTesting Guardrails...")
    
    guardrails = Guardrails()
    caller_id = "+1234567890"
    
    # Test rate limiting
    for i in range(12):
        allowed = guardrails.check_rate_limit(caller_id)
        if i < 10:
            assert allowed, f"Should allow call {i+1}"
        else:
            assert not allowed, f"Should block call {i+1}"
    
    # Test profanity filter
    assert guardrails.check_profanity("This is a test"), False
    assert guardrails.check_profanity("This is shit"), True
    
    # Test reservation validation
    valid_info = {
        "date": "2024-12-25",
        "time": "19:00",
        "party_size": 4,
        "customer_phone": "+1234567890"
    }
    is_valid, error = guardrails.validate_reservation_info(valid_info)
    assert is_valid, f"Should be valid: {error}"
    
    invalid_info = {
        "date": "invalid",
        "party_size": 25
    }
    is_valid, error = guardrails.validate_reservation_info(invalid_info)
    assert not is_valid, "Should be invalid"
    
    print("✓ Guardrails test passed")


async def test_transfer_queue():
    """Test transfer queue"""
    print("\nTesting Transfer Queue...")
    
    queue = TransferQueue()
    
    # Add staff
    staff1 = StaffMember(
        id="staff_1",
        name="Sarah",
        phone="+1234567890",
        status=StaffStatus.AVAILABLE
    )
    queue.add_staff(staff1)
    
    # Test enqueue
    request = TransferRequest(
        call_sid="test_call_1",
        caller_id="+1111111111",
        reason="Customer requested",
        context={},
        priority=TransferPriority.NORMAL
    )
    
    position = await queue.enqueue_transfer(request)
    assert position == 1, "Should be first in queue"
    
    # Test dequeue
    dequeued = await queue.dequeue_transfer()
    assert dequeued is not None, "Should dequeue request"
    assert dequeued.call_sid == "test_call_1", "Should match call SID"
    
    # Test staff assignment
    staff = await queue.assign_transfer(dequeued)
    assert staff is not None, "Should assign staff"
    assert staff.id == "staff_1", "Should assign to staff_1"
    
    print("✓ Transfer queue test passed")


async def main():
    """Run all tests"""
    print("Running component tests...\n")
    
    try:
        test_menu_rag()
        test_guardrails()
        await test_transfer_queue()
        
        print("\n✅ All tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
