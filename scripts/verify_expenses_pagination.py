
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import expenses_dao

def test_get_expenses_pagination():
    print("Testing get_expenses with offset...")
    try:
        # This call would fail with TypeError before the fix
        expenses = expenses_dao.get_expenses(limit=5, offset=0)
        print(f"Successfully called get_expenses with offset=0. Retrieved {len(expenses)} expenses.")
        
        # Test with a non-zero offset if we have enough data (optional logic, but good to check execution)
        expenses_offset = expenses_dao.get_expenses(limit=5, offset=1)
        print(f"Successfully called get_expenses with offset=1. Retrieved {len(expenses_offset)} expenses.")
        
        print("✅ Verification passed: get_expenses accepts offset argument.")
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_get_expenses_pagination()
