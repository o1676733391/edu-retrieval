import fitz

doc = fitz.open("data-samples/toan-3-tap-1.pdf")
print("Total pages in Volume 1:", len(doc))

for i in [13, 14, 15, 16, 17]:
    page = doc.load_page(i)
    print(f"Page {i}:")
    print("  Text extracted natively:", repr(page.get_text().strip()))
    print("  Number of images:", len(page.get_images()))
    pix = page.get_pixmap()
    print(f"  Pixmap size: Width={pix.width}, Height={pix.height}")
