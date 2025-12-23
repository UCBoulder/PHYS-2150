"""
JV package entry point.

Allows running the JV application as a module:
    python -m jv
    python -m jv --offline
"""

from .web_main import main

if __name__ == "__main__":
    main()
