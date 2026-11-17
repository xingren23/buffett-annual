# -*- coding: utf-8 -*-
"""Run the Buffett annual-meeting toolkit: python scripts/buffett.py --year 2024 build"""
import sys
from buffett_kit.cli import main

if __name__ == "__main__":
    main(sys.argv[1:])
