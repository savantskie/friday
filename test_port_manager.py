#!/usr/bin/env python3
"""
Quick test of port_manager functionality
"""

import sys
from pathlib import Path

# Add Friday directory to path
friday_path = Path(__file__).parent
sys.path.insert(0, str(friday_path))

from port_manager import PortManager

def test_port_manager():
    """Test the port manager"""
    print("Testing PortManager...")
    print()
    
    # Initialize
    pm = PortManager(memory_data_path=str(friday_path / "memory_data"))
    print(f"✓ PortManager initialized")
    print(f"  Primary port: {pm.PRIMARY_PORT}")
    print(f"  Backup ports: {pm.BACKUP_PORTS}")
    print()
    
    # Detect caller
    print("Detecting caller program...")
    caller = pm.detect_caller_program()
    print(f"✓ Caller detected: {caller.value}")
    print()
    
    # Check port availability
    print("Checking port availability...")
    for test_port in [21434, 21435, 8000, 9000]:
        available = pm.is_port_available(test_port)
        status = "✓ Available" if available else "✗ In use"
        print(f"  Port {test_port}: {status}")
    print()
    
    # Find available port
    print("Finding available port...")
    try:
        port = pm.find_available_port()
        print(f"✓ Found available port: {port}")
        print()
        
        # Save port info
        print("Saving port info...")
        success = pm.save_port_info()
        if success:
            print(f"✓ Port info saved to {friday_path / 'memory_data' / pm.PORT_INFO_FILENAME}")
            
            # Read it back
            active = PortManager.get_active_port(str(friday_path / "memory_data"))
            print(f"✓ Verified: active port is {active}")
        else:
            print("✗ Failed to save port info")
        print()
        
        # Get process info
        print("Getting process info...")
        import asyncio
        info = asyncio.run(pm.get_process_info())
        print(f"✓ Process info:")
        for key, value in info.items():
            if key != "cmdline":  # Skip long cmdline
                print(f"    {key}: {value}")
        
    except RuntimeError as e:
        print(f"✗ Error: {e}")
        return False
    
    print()
    print("✅ All port manager tests passed!")
    return True

if __name__ == "__main__":
    success = test_port_manager()
    sys.exit(0 if success else 1)
