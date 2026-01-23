# main.py
# Simple GUI for Mini Tensile Testing Machine

import tkinter as tk   # Import the Tkinter GUI library

# -----------------------------
# 1. Functions for the buttons
# -----------------------------

def on_start_test():
    """This function runs when the Start button is clicked."""
    status_label.config(text="Status: Test Running")   # Update the status text

def on_stop_test():
    """This function runs when the Stop button is clicked."""
    status_label.config(text="Status: Test Stopped")   # Update the status text

# -----------------------------
# 2. Create the main window
# -----------------------------

root = tk.Tk()                       # Create the main application window
root.title("Mini Tensile Machine")   # Text at the top of the window
root.geometry("600x400")             # Window size (width x height in pixels)
# If you want full screen later, you can try: root.state("zoomed")

# -----------------------------
# 3. Heading label
# -----------------------------

title_label = tk.Label(
    root,
    text="Mini Tensile Testing Machine",
    font=("Arial", 18, "bold")
)
title_label.pack(pady=20)

# -----------------------------
# 4. Load (N) labels
# -----------------------------

load_label_text = tk.Label(root, text="Load (N):", font=("Arial", 14))
load_label_text.pack()

load_value_label = tk.Label(root, text="0.00", font=("Arial", 16), fg="green")
load_value_label.pack(pady=5)

# -----------------------------
# 5. Extension (mm) labels
# -----------------------------

extension_label_text = tk.Label(root, text="Extension (mm):", font=("Arial", 14))
extension_label_text.pack()

extension_value_label = tk.Label(root, text="0.000", font=("Arial", 16), fg="blue")
extension_value_label.pack(pady=5)

# -----------------------------
# 6. Status label
# -----------------------------

status_label = tk.Label(root, text="Status: Ready", font=("Arial", 12))
status_label.pack(pady=10)

# -----------------------------
# 7. Buttons (Start / Stop)
# -----------------------------

start_button = tk.Button(
    root,
    text="Start Test",
    font=("Arial", 12),
    width=15,
    command=on_start_test    # Call this function when clicked
)
start_button.pack(padx=20, pady=10)  # padx = horizontal spacing, pady = vertical spacing

stop_button = tk.Button(
    root,
    text="Stop Test",
    font=("Arial", 12),
    width=15,
    command=on_stop_test     # Call this function when clicked
)
stop_button.pack(padx=20, pady=5)

# -----------------------------
# 8. Start the GUI event loop
# -----------------------------

root.mainloop()
