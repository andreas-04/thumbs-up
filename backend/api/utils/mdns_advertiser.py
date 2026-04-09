#!/usr/bin/env python3
"""
mDNS/Avahi service advertiser for TerraCrate.
Makes the server discoverable on the local network.
"""

import os
import platform
import socket


class MDNSAdvertiser:
    """Advertise TerraCrate service via mDNS/Avahi."""

    def __init__(self, service_name="TerraCrate File Share", port=445, service_type="_smb._tcp", hostname=None):
        """
        Initialize mDNS advertiser.

        Args:
            service_name: Human-readable service name
            port: Service port number
            service_type: Service type (default: _smb._tcp for SMB)
            hostname: mDNS hostname (default: MDNS_HOSTNAME env var or system hostname)
        """
        self.service_name = service_name
        self.port = port
        self.service_type = service_type
        self.hostname = hostname or os.environ.get("MDNS_HOSTNAME", socket.gethostname())
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

            # Get local IP
            local_ip = socket.gethostbyname(socket.gethostname())

            # Connect to system bus
            bus = dbus.SystemBus()
            server = dbus.Interface(bus.get_object("org.freedesktop.Avahi", "/"), "org.freedesktop.Avahi.Server")

            # Create entry group
            group = dbus.Interface(
                bus.get_object("org.freedesktop.Avahi", server.EntryGroupNew()), "org.freedesktop.Avahi.EntryGroup"
            )

            # Register hostname -> IP so {hostname}.local resolves on the LAN
            # without requiring the Pi's system hostname to be changed
            group.AddAddress(
                -1,  # Interface (-1 = all)
                0,  # Protocol (0 = IPv4)
                dbus.UInt32(0),  # Flags
                f"{self.hostname}.local",
                local_ip,
            )

            # Add service
            group.AddService(
                -1,  # Interface (-1 = all)
                -1,  # Protocol (-1 = both IPv4 and IPv6)
                dbus.UInt32(0),  # Flags
                self.service_name,
                self.service_type,
                "",  # Domain (empty = default)
                f"{self.hostname}.local",  # Host
                dbus.UInt16(self.port),
                [],  # TXT records
            )

            group.Commit()

            self.group = group
            self.server = server

            print("✅ mDNS service advertised via Avahi")
            print(f"   Service: {self.service_name}")
            print(f"   Type: {self.service_type}")
            print(f"   Port: {self.port}")
            print(f"   Hostname: {self.hostname}.local ({local_ip})")

        except ImportError:
            print("ℹ️  dbus-python not available — mDNS handled by host avahi-daemon")
            print(f"   Ensure hostname is set: sudo hostnamectl set-hostname {self.hostname}")
            print(f"   Service available at: https://{self.hostname}.local:{self.port}")
        except DBusException as e:
            print(f"⚠️  Failed to advertise via Avahi D-Bus: {e}")
            print(f"   Service available at: https://{self.hostname}.local:{self.port}")
        except Exception as e:
            print(f"⚠️  Unexpected error with Avahi: {e}")
            print(f"   Service available at: https://{self.hostname}.local:{self.port}")

    def _advertise_macos(self):
        """Advertise service on macOS using Bonjour."""
        try:
            import socket as sock

            from zeroconf import ServiceInfo, Zeroconf

            # Get local IP
            local_ip = sock.gethostbyname(sock.gethostname())

            # Create service info
            info = ServiceInfo(
                f"{self.service_type}.local.",
                f"{self.service_name}.{self.service_type}.local.",
                port=self.port,
                addresses=[sock.inet_aton(local_ip)],
                properties={"path": "/"},
            )

            # Register service
            zeroconf = Zeroconf()
            zeroconf.register_service(info)

            self.server = zeroconf

            print("✅ mDNS service advertised via Bonjour/Zeroconf")
            print(f"   Service: {self.service_name}")
            print(f"   Type: {self.service_type}")
            print(f"   Port: {self.port}")
            print(f"   Hostname: {self.hostname}.local")

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
            except Exception:
                pass

        if self.server and hasattr(self.server, "close"):
            try:
                self.server.close()
            except Exception:
                pass


# Example usage
if __name__ == "__main__":
    advertiser = MDNSAdvertiser(service_name="TerraCrate File Share", port=445)

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
