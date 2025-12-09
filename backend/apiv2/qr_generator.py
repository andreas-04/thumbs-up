#!/usr/bin/env python3
"""
QR Code generator for easy access to ThumbsUp server.
Generates QR codes containing access URLs with embedded tokens.
"""

import qrcode
from io import BytesIO
import base64


class QRGenerator:
    """Generate QR codes for server access URLs."""
    
    def __init__(self, base_url, token):
        """
        Initialize QR code generator.
        
        Args:
            base_url: Base server URL (e.g., https://thumbsup.local:8443)
            token: Access token to embed in URL
        """
        self.base_url = base_url.rstrip('/')
        self.token = token
    
    def generate_access_url(self, path=''):
        """
        Generate access URL with embedded token.
        Points to /auth endpoint which sets cookie and redirects.
        
        Args:
            path: Optional path to specific resource
        
        Returns:
            Full URL with token parameter
        """
        # Always use /auth endpoint for initial authentication
        url = f"{self.base_url}/auth?token={self.token}"
        return url
    
    def generate_qr_code(self, path='', box_size=10, border=4):
        """
        Generate QR code image for access URL.
        
        Args:
            path: Optional path to specific resource
            box_size: Size of each QR code box
            border: Border size in boxes
        
        Returns:
            PIL Image object
        """
        url = self.generate_access_url(path)
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=box_size,
            border=border,
        )
        qr.add_data(url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        return img
    
    def generate_qr_base64(self, path=''):
        """
        Generate QR code as base64-encoded PNG for embedding in HTML.
        
        Args:
            path: Optional path to specific resource
        
        Returns:
            Base64-encoded PNG string
        """
        img = self.generate_qr_code(path)
        
        # Convert to PNG bytes
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Encode as base64
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{img_base64}"
    
    def save_qr_code(self, filename, path=''):
        """
        Save QR code to file.
        
        Args:
            filename: Output filename
            path: Optional path to specific resource
        """
        img = self.generate_qr_code(path)
        img.save(filename)
        print(f"✅ QR code saved to {filename}")
    
    def print_ascii_qr(self, path=''):
        """
        Print QR code as ASCII art to terminal.
        
        Args:
            path: Optional path to specific resource
        """
        url = self.generate_access_url(path)
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=1,
            border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)
        
        qr.print_ascii(invert=True)


# Example usage
if __name__ == "__main__":
    # Example: Generate QR code for local server
    generator = QRGenerator(
        base_url="https://thumbsup.local:8443",
        token="example_token_12345"
    )
    
    # Print access URL
    print("Access URL:")
    print(generator.generate_access_url())
    print()
    
    # Print ASCII QR code
    print("Scan this QR code to access:")
    generator.print_ascii_qr()
    
    # Save to file
    generator.save_qr_code("access_qr.png")
