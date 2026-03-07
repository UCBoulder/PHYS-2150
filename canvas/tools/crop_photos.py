"""Interactive headshot cropper for Canvas profile photos.

Opens each photo in canvas/config/photos/ and lets you click the center of
the person's face.  Crops a square region around that point, resizes to
200x200 px (2x retina for 100px display), and saves to the same directory
with a _cropped.png suffix.

Usage:
    python canvas/tools/crop_photos.py
"""

import os
import sys
import tkinter as tk
from PIL import Image, ImageTk

PHOTOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "photos")
OUTPUT_SIZE = 200  # 2x retina for 100px CSS display
SKIP = {"placeholder.png"}


def get_photos():
    """Return list of photo paths to process, skipping already-cropped files."""
    photos = []
    for f in sorted(os.listdir(PHOTOS_DIR)):
        if f in SKIP or f.endswith("_cropped.png"):
            continue
        ext = os.path.splitext(f)[1].lower()
        if ext in (".avif", ".png", ".jpg", ".jpeg", ".webp"):
            photos.append(os.path.join(PHOTOS_DIR, f))
    return photos


def pick_center(image_path: str) -> tuple:
    """Show image in a window and return (x, y) where the user clicks.

    The image is scaled to fit the screen while preserving aspect ratio.
    Returns coordinates in the *original* image space.
    """
    img = Image.open(image_path)
    orig_w, orig_h = img.size

    # Scale to fit within 800x900 preview
    max_w, max_h = 800, 900
    scale = min(max_w / orig_w, max_h / orig_h, 1.0)
    disp_w = int(orig_w * scale)
    disp_h = int(orig_h * scale)
    disp_img = img.resize((disp_w, disp_h), Image.LANCZOS)

    result = {}

    root = tk.Tk()
    root.title(f"Click face center — {os.path.basename(image_path)}")

    tk_img = ImageTk.PhotoImage(disp_img)
    canvas = tk.Canvas(root, width=disp_w, height=disp_h)
    canvas.pack()
    canvas.create_image(0, 0, anchor=tk.NW, image=tk_img)

    label = tk.Label(root, text="Click the center of the person's face, then close or press Enter.")
    label.pack(pady=4)

    marker = [None]  # mutable ref for crosshair

    def on_click(event):
        # Map display coords back to original image coords
        orig_x = int(event.x / scale)
        orig_y = int(event.y / scale)
        result["center"] = (orig_x, orig_y)

        # Draw crosshair preview
        if marker[0]:
            canvas.delete(marker[0])
        r = 10
        marker[0] = canvas.create_oval(
            event.x - r, event.y - r, event.x + r, event.y + r,
            outline="red", width=2,
        )

        # Also draw the crop square preview
        canvas.delete("crop_preview")
        half = min(orig_w, orig_h) // 2
        # Clamp to image bounds
        cx, cy = orig_x, orig_y
        left = max(0, cx - half)
        top = max(0, cy - half)
        right = min(orig_w, cx + half)
        bottom = min(orig_h, cy + half)
        side = min(right - left, bottom - top)
        # Re-center
        left = cx - side // 2
        top = cy - side // 2
        left = max(0, min(left, orig_w - side))
        top = max(0, min(top, orig_h - side))
        # Draw in display coords
        canvas.create_rectangle(
            left * scale, top * scale,
            (left + side) * scale, (top + side) * scale,
            outline="red", width=2, dash=(4, 4), tags="crop_preview",
        )

    def on_enter(event=None):
        if "center" in result:
            root.destroy()

    canvas.bind("<Button-1>", on_click)
    root.bind("<Return>", on_enter)
    root.protocol("WM_DELETE_WINDOW", lambda: root.destroy() if "center" in result else None)

    root.mainloop()
    return result.get("center")


def crop_square(image_path: str, center: tuple) -> str:
    """Crop a square around center, resize to OUTPUT_SIZE, save as PNG."""
    img = Image.open(image_path)
    orig_w, orig_h = img.size
    cx, cy = center

    # Largest square that fits within the image centered on (cx, cy)
    half = min(cx, cy, orig_w - cx, orig_h - cy)
    # Use the smaller dimension as max half-side
    half = min(half, min(orig_w, orig_h) // 2)

    left = cx - half
    top = cy - half
    right = cx + half
    bottom = cy + half

    cropped = img.crop((left, top, right, bottom))
    cropped = cropped.resize((OUTPUT_SIZE, OUTPUT_SIZE), Image.LANCZOS)

    # Save as PNG next to the original
    base = os.path.splitext(os.path.basename(image_path))[0]
    out_path = os.path.join(PHOTOS_DIR, f"{base}_cropped.png")
    cropped.save(out_path, "PNG", optimize=True)
    return out_path


def main():
    photos = get_photos()
    if not photos:
        print("No photos to process.")
        return

    print(f"Found {len(photos)} photo(s) to crop.\n")

    for path in photos:
        name = os.path.basename(path)
        print(f"Opening {name} — click the center of the face...")
        center = pick_center(path)
        if center is None:
            print(f"  Skipped (no click registered).\n")
            continue
        out = crop_square(path, center)
        print(f"  Saved: {os.path.basename(out)}\n")

    print("Done! Update config/course_config.yaml photo fields to use the _cropped.png filenames.")


if __name__ == "__main__":
    main()
