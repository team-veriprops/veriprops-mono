"""
    Vercel adaptation
"""

from pathlib import Path

print("Current file:", __file__)
print("Current cwd:", Path.cwd())

for p in Path("/vercel/path1").rglob("firebase-service-account.json"):
    print("Found:", p)
    
from veriprops import app