import tkinter as tk  # Create GUI applications
from tkinter import ttk # Set of widgets
import serial  # To have serial communication with Python and Arduino
import serial.tools.list_ports # To detect the Arduino connected port from the available ports
import time # lets Python work with time related operations
from collections import deque # data container for live incoming readings
import csv
import os
from tkinter import filedialog # open save as window

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # place the graph inside the Tkinter window
# Tkinter builds the software window + Matplotlib builds the graph + FigureCanvasTkAgg joins them together

class TensileGUI:
    def __init__(self, root): # self=current object, root=main Tkinter window
        self.root = root # store the incoming window inside the class
        self.root.title("Mini Tensile Machine") #Title text

        self.ser = None # ser=Serial Communication
        self.running = False #tells whether the machine is currently running a test or not

        # Inputs 
        vcmd_positive = (self.root.register(self.validate_positive), "%P")
        self.L0_var = tk.StringVar(value="") # StringVar=variable for GUI input boxes
        self.A_var  = tk.StringVar(value="") #A_var=Cross section area

        # Curve selection (like SmartTest)
        self.plot_mode_var = tk.StringVar(value="Force vs Displacement") # Gave a default graph for the multiple graph types

        # Data buffers
        self.max_points = 20000 # max no of data points stored in the memory for plotting
        self.t_s    = deque(maxlen=self.max_points) # store time in s 
        self.force  = deque(maxlen=self.max_points) # store force in N
        self.disp   = deque(maxlen=self.max_points) # store displacement in mm
        self.force_window = deque(maxlen=5)
        self.disp_window = deque(maxlen=5)
        self.stress = deque(maxlen=self.max_points) # stores computed stress values
        self.strain = deque(maxlen=self.max_points) # stores computed strain values

        self.t0_ms = None # stores the starting time of the test

        # ---------------- CONTROLS ----------------
        controls_frame = ttk.Frame(self.root, padding=8) # create a Frame. padding=adds space around the contents
        #controls_frame=name of the frame
        controls_frame.grid(row=0, column=0, sticky="ew")

        # Direction buttons
        self.btn_dir_up = ttk.Button(controls_frame, text="DIR UP", command=lambda: self.set_dir("UP"))
        #lambda=temporary function that waits until the button is clicked
        self.btn_dir_up.grid(row=0, column=0, padx=5, pady=5) # padx=Adds horizontal spacing

        self.btn_dir_down = ttk.Button(controls_frame, text="DIR DOWN", command=lambda: self.set_dir("DOWN"))
        self.btn_dir_down.grid(row=0, column=1, padx=5, pady=5)

        # Zeroing buttons
        self.btn_tare = ttk.Button(controls_frame, text="TARE", command=lambda: self.send_cmd("TARE"))
        self.btn_tare.grid(row=0, column=2, padx=5, pady=5)

        self.btn_zero_len = ttk.Button(controls_frame, text="ZERO LEN", command=lambda: self.send_cmd("ZERO_LEN"))
        self.btn_zero_len.grid(row=0, column=3, padx=5, pady=5)

        # Save button
        self.btn_save = ttk.Button(controls_frame, text="EXPORT", command=self.save_data_and_plot)
        self.btn_save.grid(row=0, column=6, padx=5, pady=5)

        # Data button
        self.btn_clear = ttk.Button(controls_frame, text="CLEAR", command=self.clear_data)
        self.btn_clear.grid(row=0, column=7, padx=5, pady=5)

        # Test control buttons
        self.btn_start = ttk.Button(controls_frame, text="START", command=self.start_test)
        self.btn_start.grid(row=0, column=4, padx=5, pady=5)
        self.btn_stop = ttk.Button(controls_frame, text="STOP", command=self.stop_test)
        self.btn_stop.grid(row=0, column=5, padx=5, pady=5)
        
        # Inputs row 
        ttk.Label(controls_frame, text="L0 (mm)").grid(row=1, column=0, pady=5, sticky="e")
        # sticky="e" aligns the label to the right side of its cell
        ttk.Label(controls_frame, text="Area (mm²)").grid(row=1, column=2, pady=5, sticky="e")
        self.entry_L0 = ttk.Entry(
            controls_frame,
            textvariable=self.L0_var,
            width=10,
            validate="key", # Run the validation function every time the user presses a key
            validatecommand=vcmd_positive
        )
        self.entry_L0.grid(row=1, column=1, sticky="w")

        self.entry_A = ttk.Entry(
            controls_frame,
            textvariable=self.A_var,
            width=10,
            validate="key",
            validatecommand=vcmd_positive
        )
        self.entry_A.grid(row=1, column=3, sticky="w")

        ttk.Label(controls_frame, text="Graph Type").grid(row=1, column=4, pady=5, sticky="e")
        modes = ["Force vs Time","Displacement vs Time","Force vs Displacement","Stress vs Strain"]

        self.mode_box = ttk.Combobox(
            controls_frame,
            textvariable=self.plot_mode_var,
            values=modes,
            state="readonly", # user can only choose from the list
            width=18 # size of the dropdown box
        )
        self.mode_box.grid(row=1, column=5, padx=5, sticky="w")

        self.status_var = tk.StringVar(value="Searching for Arduino...")
        ttk.Label(controls_frame, textvariable=self.status_var).grid(row=1, column=6, sticky="w")

        # ---------------- PLOT ----------------
        fig = plt.Figure(figsize=(7, 4.5))
        self.ax = fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(fig, master=self.root)
        self.canvas.get_tk_widget().grid(row=1, column=0, padx=10, pady=10)
        # places the graph widget into the GUI layout
        self.root.grid_rowconfigure(1, weight=1) # graph expands with the window expanding
        self.root.grid_columnconfigure(0, weight=1)

        # UI state
        self.set_ui_running(False)

        # Try auto-connect once at startup
        self.auto_connect_arduino() # calls the function that searches for the Arduino and tries to connect

        # loops
        self.root.after(50, self.read_serial) # Read serial every 50 ms
        self.root.after(200, self.update_plot) # Update graph every 200 ms
        self.root.protocol("WM_DELETE_WINDOW", self.on_close) # Use on_close() when the user closes the software window

    # ----------------------------------------------------
    # AUTO DETECT ARDUINO 
    # ----------------------------------------------------
    def auto_connect_arduino(self):
        # If already connected, do nothing
        if self.ser and self.ser.is_open: # If a serial object exists and the port is open
            return True # exit immediately

        ports = [p.device for p in serial.tools.list_ports.comports()]
        # scan the computer for serial devices, get the actual port name, create a list
        if not ports:
            self.status_var.set("No Arduino detected.")
            return False

        # Try each port and look for the Arduino header
        for port in ports: # the earlier created list
            try:
                s = serial.Serial(port, 9600, timeout=0.2) # timeout=0.2:how long Python waits for incoming data
                time.sleep(1.6)  # allow Arduino reset
                try: # to prevent program from crashing
                    s.reset_input_buffer() # Clear old serial data
                except:
                    pass

                # Read a few lines to detect header
                found = False
                t0 = time.time()# Record current time
                while time.time() - t0 < 2.0: # typical reset time is 1 s
                    line = s.readline().decode(errors="ignore").strip() # reads a single line from the serial port
                    #.decode(errors="ignore"): Convertes the serial data in bytes into normal text, .strip():remove extra characters
                    if "t_ms,force_N,disp_mm" in line:
                        found = True
                        break

                if found:
                    self.ser = s
                    self.status_var.set(f"Connected to Arduino on {port}")# update the status
                    return True
                else:
                    s.close() # the loop moves to the next part

            except:
                pass

        self.status_var.set("Arduino not found. Restart after plugging Arduino.")
        return False

    # ----------------------------------------------------
    # SERIAL COMMAND
    # ----------------------------------------------------
    def send_cmd(self, cmd):  # cmd=command text that should be sent to Arduino
        if not self.auto_connect_arduino():
            return False
        try:
            self.ser.write((cmd + "\n").encode())  # .encode: Convert text to bytes
            return True
        except serial.SerialException as e:
            self.status_var.set(f"Send error: {e}")  # Error handling
            return False

    # ----------------------------------------------------
    # UI STATE  : Idle state or Running state
    # ----------------------------------------------------
    def set_ui_running(self, running: bool): # True:machine is running
        self.running = running
        if running:
            self.btn_start.state(["disabled"]) # Disable buttons
            self.btn_stop.state(["!disabled"]) # Remove disable
            self.btn_dir_up.state(["disabled"])
            self.btn_dir_down.state(["disabled"])
        else:
            self.btn_start.state(["!disabled"]) # Only Enable START button
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

    def validate_positive(self, value):
        if value == "":
            return True

        if value.count(".") > 1:
            return False

        if value == ".":
            return False

        allowed_chars = "0123456789." # to make 0.123 also possible
        if any(ch not in allowed_chars for ch in value):
            return False

        try:
            float(value)
        except ValueError:
            return False

        return True

    # ----------------------------------------------------
    # START / STOP
    # ----------------------------------------------------
    def start_test(self):
        mode = self.plot_mode_var.get()
        L0_text = self.L0_var.get().strip()
        A_text = self.A_var.get().strip()

        if mode == "Stress vs Strain":
            if L0_text == "" or A_text == "":
                self.status_var.set("Enter L0 and Area for Stress-Strain")
                return

            try:
                L0 = float(L0_text)
                A = float(A_text)
            except ValueError:
                self.status_var.set("L0 and Area must be numbers")
                return

            if L0 <= 0 or A <= 0:
                self.status_var.set("L0 and Area must be > 0")
                return

        if self.send_cmd("START"):
            self.set_ui_running(True)
            self.status_var.set("RUNNING...")


    def stop_test(self):
        if self.send_cmd("STOP"):
            self.set_ui_running(False)
            self.status_var.set("STOPPED")

    def clear_data(self):
        self.t_s.clear() # empties the time buffer
        self.force.clear()
        self.disp.clear()
        self.force_window.clear()
        self.disp_window.clear()
        self.stress.clear()
        self.strain.clear()
        self.t0_ms = None # Reset time reference
        self.status_var.set("Cleared")
    
    def save_data_and_plot(self):
        if len(self.t_s) == 0:
            self.status_var.set("No data to save")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save data and plot"
        )

        if not file_path:
            self.status_var.set("Save cancelled")
            return

        try:
            # Split the selected path into folder + filename without extension
            base_path, _ = os.path.splitext(file_path)

            csv_path = base_path + ".csv"
            png_path = base_path + ".png"

            # Save CSV
            with open(csv_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Time (s)", "Force (N)", "Displacement (mm)", "Strain", "Stress (MPa)"])

                for row in zip(self.t_s, self.force, self.disp, self.strain, self.stress):
                    writer.writerow(row)

            # Save current plot
            self.ax.figure.savefig(png_path, dpi=300, bbox_inches="tight")

            self.status_var.set(f"Saved: {os.path.basename(csv_path)} and {os.path.basename(png_path)}")

        except Exception as e:
            self.status_var.set(f"Save error: {e}")

    # ----------------------------------------------------
    # READ SERIAL
    # ----------------------------------------------------
    def read_serial(self):
        if self.ser and self.ser.is_open:  # serial object exists and Port is open
            try:
                while self.ser.in_waiting:
                    line = self.ser.readline().decode(errors="ignore").strip()
                    # decode(): bytes to string
                    if not line:
                        continue

                    # Ignore non-data lines
                    if line.startswith("OK") or line.startswith("ERR") or line.startswith("BOOT"):
                        # ignore OK, ERR, BOOT msgs sent by Arduino
                        self.status_var.set(line)
                        continue
                    if line.lower().startswith("t_ms"):  # Ignore header line
                        continue

                    parts = line.split(",")  # Split the data
                    if len(parts) != 3:  # check whether time, force, and displacement values are present
                        continue

                    try:
                        t_ms = int(float(parts[0]))
                        forceN = float(parts[1])
                        dispMM = float(parts[2])
                    except:  # error handling
                        continue

                    if dispMM < 0:
                        continue

                    if self.t0_ms is None:
                        self.t0_ms = t_ms  # First data point becomes time = 0
                    t_sec = (t_ms - self.t0_ms) / 1000.0  # convert to seconds

                    # Store last 5 readings
                    self.force_window.append(forceN)
                    self.disp_window.append(dispMM)

                    # Only process when 5 values available
                    if len(self.force_window) == 5:
                        avg_force = sum(self.force_window) / 5
                        avg_disp = sum(self.disp_window) / 5

                        self.t_s.append(t_sec)
                        self.force.append(avg_force)
                        self.disp.append(avg_disp)

                        # stress/strain
                        try:
                            L0_txt = self.L0_var.get().strip()
                            A_txt = self.A_var.get().strip()

                            if L0_txt and A_txt:  # only continue if both input boxes contain something
                                L0 = float(L0_txt)
                                A = float(A_txt)

                                if L0 > 0 and A > 0:
                                    # Calculate strain and stress
                                    self.strain.append(avg_disp / L0)
                                    self.stress.append(avg_force / A)
                                else:
                                    self.strain.append(0.0)
                                    self.stress.append(0.0)
                            else:
                                self.strain.append(0.0)
                                self.stress.append(0.0)
                        except:
                            self.strain.append(0.0)
                            self.stress.append(0.0)

            except Exception as e:  # Read the error
                self.status_var.set(f"Read error: {e}")
                # Reset serial object so auto_connect_arduino() can
                # attempt a fresh reconnect on the next read_serial cycle.
                # Without this, self.ser.is_open may still appear True on a
                # broken/disconnected port, blocking any reconnect attempt.
                self.ser = None

        self.root.after(50, self.read_serial)  # run read_serial again and again in 50 ms

    # ----------------------------------------------------
    # PLOT
    #  clears the axes completely on every update,then redraws a fresh line. 
    # ----------------------------------------------------
    def update_plot(self):
        mode = self.plot_mode_var.get()

        # Clear the axes completely so no stale lines or labels remain when the user switches between graph modes
        self.ax.cla()

        if mode == "Force vs Time":
            x = list(self.t_s)
            y = list(self.force)
            self.ax.set_xlabel("Time (s)")
            self.ax.set_ylabel("Force (N)")

        elif mode == "Displacement vs Time":
            x = list(self.t_s)
            y = list(self.disp)
            self.ax.set_xlabel("Time (s)")
            self.ax.set_ylabel("Displacement (mm)")

        elif mode == "Force vs Displacement":
            x = list(self.disp)
            y = list(self.force)
            self.ax.set_xlabel("Displacement (mm)")
            self.ax.set_ylabel("Force (N)")

        elif mode == "Stress vs Strain":
            x = list(self.strain)
            y = list(self.stress)
            self.ax.set_xlabel("Strain (ΔL/L0)")
            self.ax.set_ylabel("Stress (MPa)")

        else:
            x = []
            y = []  # Fallback case to prevent crashing

        # Set title to current mode so user always knows what is displayed
        self.ax.set_title(mode)
        self.ax.grid(True)

        # Plot a fresh line each frame (replaces the old self.line.set_data approach)
        self.ax.plot(x, y)

        self.ax.relim()           # Recalculate axis limits
        self.ax.autoscale_view()  # Auto range (no manual range needed)
        self.canvas.draw()        # Refresh the graph on the screen

        self.root.after(200, self.update_plot)

    def on_close(self): # This runs when the window is closed. 
        #Safely stop the machine and close the serial connection
        try: # Send STOP to Arduino
            if self.ser and self.ser.is_open:
                self.ser.write(b"STOP\n")
                time.sleep(0.1)
        except:
            pass
        try: # Close serial port
            if self.ser and self.ser.is_open:
                self.ser.close()
        except:
            pass
        self.root.destroy() # closes the GUI window and ends the application


if __name__ == "__main__":
    root = tk.Tk()
    root.state('zoomed') # to get the full screen
    app = TensileGUI(root)# pass the window (root) into the class
    root.mainloop()