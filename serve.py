#!/usr/bin/env python3
"""
Agda Lemma Search - HTTP Server
Launches the search interface on http://localhost:8002
"""
import http.server
import socketserver
import webbrowser
import os
import sys

def main():
    PORT = 8002
    
    # Change to the directory containing this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Check if search.html exists
    if not os.path.exists('search.html'):
        print("❌ Error: search.html not found!")
        print("Make sure you're running this from the agda-search directory.")
        sys.exit(1)
    
    print("🚀 Starting Agda Lemma Search...")
    print(f"📁 Serving from: {script_dir}")
    print(f"🌐 URL: http://localhost:{PORT}/search.html")
    print("Press Ctrl+C to stop the server")
    
    try:
        with socketserver.TCPServer(("", PORT), http.server.SimpleHTTPRequestHandler) as httpd:
            print(f"✅ Server running on port {PORT}")
            
            # Open browser
            webbrowser.open(f'http://localhost:{PORT}/search.html')
            
            httpd.serve_forever()
            
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"❌ Port {PORT} is already in use!")
            print("Try closing other instances or use a different port.")
        else:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
