import barcode
from barcode import EAN13
from barcode.writer import ImageWriter
from io import BytesIO

try:
    number = '123456789012'
    my_code = EAN13(number, writer=ImageWriter())
    buffer = BytesIO()
    my_code.write(buffer)
    print("Code execution successful")
except Exception as e:
    print(f"Error: {e}")
