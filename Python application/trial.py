import tkinter as tk
from tkinter import ttk
import serial
import serial.tools.list_ports
import time
from collections import deque

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # allows a Matplotlib graph to be embedded inside a Tkinter window


class TensileGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Mini Tensile Machine - Live Stress–Strain")

        self.ser = None
        self.connected_port = None

        # ---- Leave blank initially (as you requested) ----
        self.L0_var = tk.StringVar(value="")   # mm
        self.A_var  = tk.StringVar(value="")   # mm^2

        # ---- Optional speed control (microseconds) ----
        self.spd_var = tk.StringVar(value="800")  # matches Arduino default in the improved sketch

        # ---- Data buffers ----
        self.max_points = 2000
        self.strain = deque(maxlen=self.max_points)
        self.stress = deque(maxlen=self.max_points)

        # ---- Optional: raw streaming buffers (useful later for logging) ----
        self.t_ms_buf = deque(maxlen=self.max_points)
        self.force_buf = deque(maxlen=self.max_points)
        self.disp_buf = deque(maxlen=self.max_points)

        # ---------------- TOP BAR ----------------
        top = ttk.Frame(root, padding=8)
        top.grid(row=0, column=0, sticky="ew")

        ttk.Label(top, text="Port").grid(row=0, column=0)
        self.port_var = tk.StringVar()
        self.port_box = ttk.Combobox(top, textvariable=self.port_var, width=12, state="readonly")
        self.port_box.grid(row=0, column=1, padx=5)

        ttk.Button(top, text="Refresh", command=self.refresh_ports).grid(row=0, column=2, padx=5)
        ttk.Button(top, text="Connect", command=self.connect).grid(row=0, column=3, padx=5)

        # -------- Direction buttons --------
        ttk.Button(top, text="DIR UP", command=lambda: self.send_cmd("DIR UP")).grid(row=0, column=4, padx=5)
        ttk.Button(top, text="DIR DOWN", command=lambda: self.send_cmd("DIR DOWN")).grid(row=0, column=5, padx=5)

        # -------- Main controls --------
        ttk.Button(top, text="Tare", command=lambda: self.send_cmd("TARE")).grid(row=0, column=6, padx=5)
        ttk.Button(top, text="Zero Len", command=lambda: self.send_cmd("ZERO_LEN")).grid(row=0, column=7, padx=5)
        ttk.Button(top, text="Stop", command=lambda: self.send_cmd("STOP")).grid(row=0, column=8, padx=5)
        ttk.Button(top, text="Start", command=self.start_with_checks).grid(row=0, column=9, padx=5)

        ttk.Button(top, text="Clear Plot", command=self.clear_plot).grid(row=0, column=10, padx=5)

        # ---- L0 and Area inputs (blank initially) ----
        ttk.Label(top, text="L0 (mm)").grid(row=1, column=0, pady=5, sticky="e")
        ttk.Entry(top, textvariable=self.L0_var, width=10).grid(row=1, column=1, sticky="w")

        ttk.Label(top, text="Area A (mm²)").grid(row=1, column=2, pady=5, sticky="e")
        ttk.Entry(top, textvariable=self.A_var, width=10).grid(row=1, column=3, sticky="w")

        # ---- Speed input ----
        ttk.Label(top, text="SPD (µs)").grid(row=1, column=4, pady=5, sticky="e")
        ttk.Entry(top, textvariable=self.spd_var, width=10).grid(row=1, column=5, sticky="w")
        ttk.Button(top, text="Set SPD", command=self.set_speed).grid(row=1, column=6, padx=5)

        self.status_var = tk.StringVar(value="Not connected")
        ttk.Label(top, textvariable=self.status_var).grid(row=1, column=7, columnspan=4, sticky="w")

        # ---------------- PLOT ----------------
        fig = plt.Figure(figsize=(7, 4.5))
        self.ax = fig.add_subplot(111)
        self.ax.set_xlabel("Strain (ΔL/L0)")
        self.ax.set_ylabel("Stress (MPa)")
        self.line, = self.ax.plot([], [])

        self.canvas = FigureCanvasTkAgg(fig, master=root)
        self.canvas.get_tk_widget().grid(row=1, column=0, padx=10, pady=10)

        # ---------------- LIVE VALUES ----------------
        bottom = ttk.Frame(root, padding=8)
        bottom.grid(row=2, column=0, sticky="ew")

        self.last_force_var = tk.StringVar(value="Force: -- N")
        self.last_disp_var  = tk.StringVar(value="Disp: -- mm")
        ttk.Label(bottom, textvariable=self.last_force_var).grid(row=0, column=0, padx=10)
        ttk.Label(bottom, textvariable=self.last_disp_var).grid(row=0, column=1, padx=10)

        # Start loops
        self.refresh_ports()
        self.root.after(50, self.read_serial_nonblocking)
        self.root.after(200, self.update_plot)

        # Make close safe (stop motor if running)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_box["values"] = ports
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])

    def connect(self):
        port = self.port_var.get().strip()
        if not port:
            self.status_var.set("Select a port")
            return
        try:
            # Close old connection if any
            if self.ser:
                try:
                    self.ser.close()
                except:
                    pass
                self.ser = None

            self.ser = serial.Serial(port, 9600, timeout=0.05)
            self.connected_port = port
            time.sleep(1.7)  # Arduino reset delay

            # Flush any boot garbage / partial lines after reset
            try:
                self.ser.reset_input_buffer()
            except:
                pass

            self.status_var.set(f"Connected: {port}")
        except Exception as e:
            self.status_var.set(f"Connect failed: {e}")
            self.ser = None
            self.connected_port = None

    def send_cmd(self, cmd):
        if not self.ser:
            self.status_var.set("Not connected")
            return
        try:
            self.ser.write((cmd + "\n").encode())
            self.status_var.set(f"Sent: {cmd}")
        except Exception as e:
            self.status_var.set(f"Send error: {e}")

    def set_speed(self):
        if not self.ser:
            self.status_var.set("Not connected")
            return
        txt = self.spd_var.get().strip()
        if txt == "":
            self.status_var.set("Enter SPD (µs)")
            return
        try:
            val = int(float(txt))
            if val < 200 or val > 10000:
                self.status_var.set("SPD must be 200–10000 µs")
                return
            self.send_cmd(f"SPD {val}")
        except:
            self.status_var.set("SPD must be a number")

    def clear_plot(self):
        self.strain.clear()
        self.stress.clear()
        self.t_ms_buf.clear()
        self.force_buf.clear()
        self.disp_buf.clear()
        self.last_force_var.set("Force: -- N")
        self.last_disp_var.set("Disp: -- mm")
        self.status_var.set("Cleared plot/data")

    def start_with_checks(self):
        # Block START until L0 and Area are entered
        if not self.ser:
            self.status_var.set("Not connected")
            return

        L0_txt = self.L0_var.get().strip()
        A_txt  = self.A_var.get().strip()

        if L0_txt == "" or A_txt == "":
            self.status_var.set("Enter L0 and Area before START")
            return

        try:
            L0 = float(L0_txt)
            A  = float(A_txt)
            if L0 <= 0 or A <= 0:
                self.status_var.set("L0 and Area must be > 0")
                return
        except:
            self.status_var.set("L0 and Area must be numbers")
            return

        # Optionally set speed before starting (if entered)
        self.set_speed()

        # OK -> start
        self.send_cmd("START")

    def _handle_text_line(self, line: str):
        # Show OK/ERR messages in status
        u = line.strip()
        if not u:
            return

        # Ignore boot/header but still allow you to see them if you want
        if u.startswith("BOOT"):
            self.status_var.set(u)
            return
        if u.lower().startswith("t_ms"):
            return

        if u.startswith("OK") or u.startswith("ERR"):
            self.status_var.set(u)
            return

        # Expect CSV: time_ms,force_N,disp_mm
        parts = u.split(",")
        if len(parts) != 3:
            return

        try:
            t_ms = int(float(parts[0]))
            forceN = float(parts[1])
            dispMM = float(parts[2])
        except:
            return

        # live labels
        self.last_force_var.set(f"Force: {forceN:.3f} N")
        self.last_disp_var.set(f"Disp: {dispMM:.3f} mm")

        # store raw buffers (useful for later logging)
        self.t_ms_buf.append(t_ms)
        self.force_buf.append(forceN)
        self.disp_buf.append(dispMM)

        # Compute stress-strain only if L0 and A filled correctly
        L0_txt = self.L0_var.get().strip()
        A_txt  = self.A_var.get().strip()
        if L0_txt and A_txt:
            try:
                L0 = float(L0_txt)
                A  = float(A_txt)
                if L0 > 0 and A > 0:
                    strain = dispMM / L0
                    stress = forceN / A  # MPa if A in mm^2
                    self.strain.append(strain)
                    self.stress.append(stress)
            except:
                pass

    def read_serial_nonblocking(self):
        if self.ser:
            try:
                # R
