import tkinter as tk
from tkinter import ttk
import serial
import serial.tools.list_ports
import time
from collections import deque

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class TensileGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Mini Tensile Machine")

        self.ser = None
        self.running = False

        # Inputs (blank until needed)
        self.L0_var = tk.StringVar(value="")
        self.A_var  = tk.StringVar(value="")

        # Curve selection (like SmartTest)
        self.plot_mode_var = tk.StringVar(value="Load-Displacement")

        # Data buffers
        self.max_points = 2000
        self.t_s    = deque(maxlen=self.max_points)
        self.force  = deque(maxlen=self.max_points)
        self.disp   = deque(maxlen=self.max_points)
        self.stress = deque(maxlen=self.max_points)
        self.strain = deque(maxlen=self.max_points)

        self.t0_ms = None

        # ---------------- CONTROLS ----------------
        top = ttk.Frame(root, padding=8)
        top.grid(row=0, column=0, sticky="ew")

        # Direction buttons
        self.btn_dir_up = ttk.Button(top, text="DIR UP", command=lambda: self.set_dir("UP"))
        self.btn_dir_up.grid(row=0, column=0, padx=5)

        self.btn_dir_down = ttk.Button(top, text="DIR DOWN", command=lambda: self.set_dir("DOWN"))
        self.btn_dir_down.grid(row=0, column=1, padx=5)

        ttk.Button(top, text="TARE", command=lambda: self.send_cmd("TARE")).grid(row=0, column=2, padx=5)
        ttk.Button(top, text="ZERO LEN", command=lambda: self.send_cmd("ZERO_LEN")).grid(row=0, column=3, padx=5)

        self.btn_stop = ttk.Button(top, text="STOP", command=self.stop_test)
        self.btn_stop.grid(row=0, column=4, padx=5)

        self.btn_start = ttk.Button(top, text="START", command=self.start_test)
        self.btn_start.grid(row=0, column=5, padx=5)

        ttk.Button(top, text="CLEAR", command=self.clear_data).grid(row=0, column=6, padx=5)

        # Inputs row (only used for stress/strain)
        ttk.Label(top, text="L0 (mm)").grid(row=1, column=0, pady=5, sticky="e")
        ttk.Entry(top, textvariable=self.L0_var, width=10).grid(row=1, column=1, sticky="w")

        ttk.Label(top, text="Area (mm²)").grid(row=1, column=2, pady=5, sticky="e")
        ttk.Entry(top, textvariable=self.A_var, width=10).grid(row=1, column=3, sticky="w")

        ttk.Label(top, text="Curve").grid(row=1, column=4, pady=5, sticky="e")
        modes = ["Load-Time", "Displacement-Time", "Load-Displacement", "Stress-Strain"]
        self.mode_box = ttk.Combobox(top, textvariable=self.plot_mode_var, values=modes, state="readonly", width=18)
        self.mode_box.grid(row=1, column=5, padx=5, sticky="w")

        self.status_var = tk.StringVar(value="Searching for Arduino...")
        ttk.Label(top, textvariable=self.status_var).grid(row=1, column=6, sticky="w")

        # ---------------- PLOT ----------------
        fig = plt.Figure(figsize=(7, 4.5))
        self.ax = fig.add_subplot(111)
        self.line, = self.ax.plot([], [])
        self.canvas = FigureCanvasTkAgg(fig, master=root)
        self.canvas.get_tk_widget().grid(row=1, column=0, padx=10, pady=10)

        # UI state
        self.set_ui_running(False)

        # Try auto-connect once at startup
        self.auto_connect_arduino()

        # loops
        self.root.after(50, self.read_serial)
        self.root.after(200, self.update_plot)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ----------------------------------------------------
    # AUTO DETECT ARDUINO (no port dropdown)
    # ----------------------------------------------------
    def auto_connect_arduino(self):
        # If already connected, do nothing
        if self.ser and self.ser.is_open:
            return True

        ports = [p.device for p in serial.tools.list_ports.comports()]
        if not ports:
            self.status_var.set("No serial device found. Plug Arduino and restart.")
            return False

        # Try each port and look for the Arduino header
        for port in ports:
            try:
                s = serial.Serial(port, 9600, timeout=0.2)
                time.sleep(1.6)  # allow Arduino reset
                try:
                    s.reset_input_buffer()
                except:
                    pass

                # Read a few lines to detect header
                found = False
                t0 = time.time()
                while time.time() - t0 < 2.0:
                    line = s.readline().decode(errors="ignore").strip()
                    if "t_ms,force_N,disp_mm" in line:
                        found = True
                        break

                if found:
                    self.ser = s
                    self.status_var.set(f"Connected to Arduino on {port}")
                    return True
                else:
                    s.close()

            except:
                pass

        self.status_var.set("Arduino not found (no header). Restart after plugging Arduino.")
        return False

    # ----------------------------------------------------
    # SERIAL COMMAND
    # ----------------------------------------------------
    def send_cmd(self, cmd):
        if not self.auto_connect_arduino():
            return
        try:
            self.ser.write((cmd + "\n").encode())
        except Exception as e:
            self.status_var.set(f"Send error: {e}")

    # ----------------------------------------------------
    # UI STATE
    # ----------------------------------------------------
    def set_ui_running(self, running: bool):
        self.running = running
        if running:
            self.btn_start.state(["disabled"])
            self.btn_stop.state(["!disabled"])
            self.btn_dir_up.state(["disabled"])
            self.btn_dir_down.state(["disabled"])
        else:
            self.btn_start.state(["!disabled"])
            self.btn_stop.state(["disabled"])
            self.btn_dir_up.state(["!disabled"])
            self.btn_dir_down.state(["!disabled"])

    def set_dir(self, direction):
        if self.running:
            self.status_var.set("Stop first to change direction")
            return
        if direction == "UP":
            self.send_cmd("DIR UP")
            self.status_var.set("Direction = UP")
        else:
            self.send_cmd("DIR DOWN")
            self.status_var.set("Direction = DOWN")

    # ----------------------------------------------------
    # START / STOP
    # ----------------------------------------------------
    def start_test(self):
        mode = self.plot_mode_var.get()
        if mode == "Stress-Strain":
            if self.L0_var.get().strip() == "" or self.A_var.get().strip() == "":
                self.status_var.set("Enter L0 and Area for Stress-Strain")
                return
            try:
                L0 = float(self.L0_var.get()); A = float(self.A_var.get())
                if L0 <= 0 or A <= 0:
                    self.status_var.set("L0 and Area must be > 0")
                    return
            except:
                self.status_var.set("L0 and Area must be numbers")
                return

        self.send_cmd("START")
        self.set_ui_running(True)
        self.status_var.set("RUNNING...")

    def stop_test(self):
        self.send_cmd("STOP")
        self.set_ui_running(False)
        self.status_var.set("STOPPED")

    def clear_data(self):
        self.t_s.clear()
        self.force.clear()
        self.disp.clear()
        self.stress.clear()
        self.strain.clear()
        self.t0_ms = None
        self.status_var.set("Cleared")

    # ----------------------------------------------------
    # READ SERIAL
    # ----------------------------------------------------
    def read_serial(self):
        if self.ser and self.ser.is_open:
            try:
                while self.ser.in_waiting:
                    line = self.ser.readline().decode(errors="ignore").strip()
                    if not line:
                        continue

                    # Ignore non-data lines
                    if line.startswith("OK") or line.startswith("ERR") or line.startswith("BOOT"):
                        self.status_var.set(line)
                        continue
                    if line.lower().startswith("t_ms"):
                        continue

                    parts = line.split(",")
                    if len(parts) != 3:
                        continue

                    try:
                        t_ms = int(float(parts[0]))
                        forceN = float(parts[1])
                        dispMM = float(parts[2])
                    except:
                        continue

                    if self.t0_ms is None:
                        self.t0_ms = t_ms
                    t_sec = (t_ms - self.t0_ms) / 1000.0

                    self.t_s.append(t_sec)
                    self.force.append(forceN)
                    self.disp.append(dispMM)

                    # stress/strain
                    try:
                        L0_txt = self.L0_var.get().strip()
                        A_txt  = self.A_var.get().strip()
                        if L0_txt and A_txt:
                            L0 = float(L0_txt); A = float(A_txt)
                            if L0 > 0 and A > 0:
                                self.strain.append(dispMM / L0)
                                self.stress.append(forceN / A)
                            else:
                                self.strain.append(0.0); self.stress.append(0.0)
                        else:
                            self.strain.append(0.0); self.stress.append(0.0)
                    except:
                        self.strain.append(0.0); self.stress.append(0.0)

            except Exception as e:
                self.status_var.set(f"Read error: {e}")

        self.root.after(50, self.read_serial)

    # ----------------------------------------------------
    # PLOT
    # ----------------------------------------------------
    def update_plot(self):
        mode = self.plot_mode_var.get()

        if mode == "Load-Time":
            x = list(self.t_s); y = list(self.force)
            self.ax.set_xlabel("Time (s)")
            self.ax.set_ylabel("Load (N)")

        elif mode == "Displacement-Time":
            x = list(self.t_s); y = list(self.disp)
            self.ax.set_xlabel("Time (s)")
            self.ax.set_ylabel("Displacement (mm)")

        elif mode == "Load-Displacement":
            x = list(self.disp); y = list(self.force)
            self.ax.set_xlabel("Displacement (mm)")
            self.ax.set_ylabel("Load (N)")

        elif mode == "Stress-Strain":
            x = list(self.strain); y = list(self.stress)
            self.ax.set_xlabel("Strain (ΔL/L0)")
            self.ax.set_ylabel("Stress (MPa)")

        else:
            x = []; y = []

        self.line.set_data(x, y)
        self.ax.relim()               # recompute limits based on data
        self.ax.autoscale_view()      # auto range (no manual range needed)
        self.canvas.draw()

        self.root.after(200, self.update_plot)

    def on_close(self):
        try:
            if self.ser and self.ser.is_open:
                self.ser.write(b"STOP\n")
                time.sleep(0.1)
        except:
            pass
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except:
            pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = TensileGUI(root)
    root.mainloop()
