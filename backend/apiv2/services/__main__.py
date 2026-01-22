#!/usr/bin/env python3
"""
SMB Manager - Standalone entry point
Can be run directly: python3 -m services.smb_manager
"""

if __name__ == "__main__":
    from services.smb_manager import SMBManager
    from pathlib import Path
    import os
    
    # Get storage path (relative to apiv2/)
    storage_path = Path(__file__).parent.parent / "storage"
    
    # Get credentials from environment or use defaults
    guest_user = os.getenv('SMB_GUEST_USER', 'guest')
    guest_pass = os.getenv('SMB_GUEST_PASSWORD', 'guest')
    
    print("=" * 50)
    print("ThumbsUp SMB Server - Standalone Mode")
    print("=" * 50)
    print()
    
    # Initialize manager
    manager = SMBManager(
        storage_path=str(storage_path),
        service_name="ThumbsUp File Share"
    )
    
    # Show connection info
    info = manager.get_connection_info()
    print("Configuration:")
    print(f"  Storage: {info['storage_path']}")
    print(f"  Username: {info['username']}")
    print(f"  Password: {info['password']}")
    print(f"  Share URL: {info['url']}")
    print()
    
    # Start service
    process = manager.start_service()
    
    if process:
        print()
        print("✅ SMB Server is running!")
        print("   Press Ctrl+C to stop...")
        print()
        
        try:
            # Keep process running
            for line in process.stdout:
                print(f"[SMB] {line.rstrip()}")
        except KeyboardInterrupt:
            print("\n🛑 Stopping SMB server...")
            manager.stop_service()
            print("✅ Server stopped")
    else:
        print("❌ Failed to start SMB server")
        exit(1)
