#!/usr/bin/env python3
"""
mDNS/Avahi service advertiser for ThumbsUp.
Makes the server discoverable on the local network.
"""

import socket
import sys
import platform


class MDNSAdvertiser:
    """Advertise ThumbsUp service via mDNS/Avahi."""
    
    def __init__(self, service_name="ThumbsUp File Share", port=445, service_type="_smb._tcp"):
        """
        Initialize mDNS advertiser.
        
        Args:
            service_name: Human-readable service name
            port: Service port number
            service_type: Service type (default: _smb._tcp for SMB)
        """
        self.service_name = service_name
        self.port = port
        self.service_type = service_type
        self.hostname = socket.gethostname()
        self.group = None
        self.server = None
    
    def advertise(self):
        """
        Start advertising the service via mDNS.
        Platform-specific implementation.
        """
        system = platform.system()
        
        if system == "Darwin":  # macOS
            self._advertise_macos()
        elif system == "Linux":
            self._advertise_linux()
        elif system == "Windows":
            self._advertise_windows()
        else:
            print(f"⚠️  mDNS not supported on {system}")
            print(f"   Service available at: https://{self.hostname}:{self.port}")
    
    def _advertise_linux(self):
        """Advertise service on Linux using Avahi."""
        try:
            import dbus
            from dbus import DBusException
            
            # Connect to system bus
            bus = dbus.SystemBus()
            server = dbus.Interface(
                bus.get_object('org.freedesktop.Avahi', '/'),
                'org.freedesktop.Avahi.Server'
            )
            
            # Create entry group
            group = dbus.Interface(
                bus.get_object('org.freedesktop.Avahi', server.EntryGroupNew()),
                'org.freedesktop.Avahi.EntryGroup'
            )
            
            # Add service
            group.AddService(
                -1,  # Interface (-1 = all)
                -1,  # Protocol (-1 = both IPv4 and IPv6)
                dbus.UInt32(0),  # Flags
                self.service_name,
                self.service_type,
                "",  # Domain (empty = default)
                "",  # Host (empty = localhost)
                dbus.UInt16(self.port),
                []   # TXT records
            )
            
            group.Commit()
            
            self.group = group
            self.server = server
            
            print(f"✅ mDNS service advertised via Avahi")
            print(f"   Service: {self.service_name}")
            print(f"   Type: {self.service_type}")
            print(f"   Port: {self.port}")
            print(f"   Hostname: {self.hostname}.local")
            
        except ImportError:
            print("⚠️  Avahi (dbus-python) not available")
            print("   Install with: pip install dbus-python")
            print(f"   Service available at: https://{self.hostname}:{self.port}")
        except DBusException as e:
            print(f"⚠️  Failed to advertise via Avahi: {e}")
            print("   Make sure avahi-daemon is running:")
            print("   sudo systemctl start avahi-daemon")
            print(f"   Service available at: https://{self.hostname}:{self.port}")
        except Exception as e:
            print(f"⚠️  Unexpected error with Avahi: {e}")
            print(f"   Service available at: https://{self.hostname}:{self.port}")
    
    def _advertise_macos(self):
        """Advertise service on macOS using Bonjour."""
        try:
            from zeroconf import ServiceInfo, Zeroconf
            import socket as sock
            
            # Get local IP
            hostname = sock.gethostname()
            local_ip = sock.gethostbyname(hostname)
            
            # Create service info
            info = ServiceInfo(
                f"{self.service_type}.local.",
                f"{self.service_name}.{self.service_type}.local.",
                port=self.port,
                addresses=[sock.inet_aton(local_ip)],
                properties={'path': '/'},
            )
            
            # Register service
            zeroconf = Zeroconf()
            zeroconf.register_service(info)
            
            self.server = zeroconf
            
            print(f"✅ mDNS service advertised via Bonjour/Zeroconf")
            print(f"   Service: {self.service_name}")
            print(f"   Type: {self.service_type}")
            print(f"   Port: {self.port}")
            print(f"   Hostname: {hostname}.local")
            
        except ImportError:
            print("⚠️  Zeroconf not available (optional on macOS)")
            print("   Bonjour is built-in, service should still be discoverable")
            print(f"   Service available at: https://{self.hostname}.local:{self.port}")
        except Exception as e:
            print(f"⚠️  Failed to advertise via Zeroconf: {e}")
            print(f"   Service available at: https://{self.hostname}.local:{self.port}")
    
    def _advertise_windows(self):
        """Advertise service on Windows."""
        print("ℹ️  mDNS on Windows requires Bonjour Print Services or iTunes")
        print(f"   Service should be accessible at: https://{self.hostname}.local:{self.port}")
        print(f"   Or use IP directly: https://{socket.gethostbyname(self.hostname)}:{self.port}")
    
    def stop(self):
        """Stop advertising the service."""
        if self.group:
            try:
                self.group.Reset()
                print("✅ mDNS service advertisement stopped")
            except:
                pass
        
        if self.server and hasattr(self.server, 'close'):
            try:
                self.server.close()
            except:
                pass


# Example usage
if __name__ == "__main__":
    advertiser = MDNSAdvertiser(
        service_name="ThumbsUp File Share",
        port=445
    )
    
    try:
        advertiser.advertise()
        print("\nPress Ctrl+C to stop advertising...")
        
        # Keep running
        import time
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\nStopping...")
        advertiser.stop()
