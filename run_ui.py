#!/usr/bin/env python3
"""
Launch the VPR Web UI.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vpr.ui.server import app

if __name__ == "__main__":
    print("=" * 60)
    print("🎬 Video Product Recorder - Web UI")
    print("=" * 60)
    print()
    print("🚀 Starting server...")
    print("📱 Open your browser and navigate to:")
    print()
    print("   http://localhost:5001")
    print()
    print("=" * 60)
    print()

    app.run(debug=True, host="0.0.0.0", port=5001)
