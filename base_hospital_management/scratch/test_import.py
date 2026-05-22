try:
    from barcode import EAN13
    from barcode.writer import ImageWriter
    print("Import successful")
except ImportError as e:
    print(f"Import failed: {e}")
