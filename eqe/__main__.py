"""
EQE package entry point.

Allows running the EQE application as a module:
    python -m eqe
    python -m eqe --offline
"""

from .main import main

if __name__ == "__main__":
    main()
