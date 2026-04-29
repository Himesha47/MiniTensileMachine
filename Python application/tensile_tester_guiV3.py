import tkinter as tk                          # Create GUI applications
from tkinter import ttk                      # Set of themed widgets
import serial                                # Serial communication with Arduino
import serial.tools.list_ports              # Detect which port the Arduino is on
import time                                  # Time-related operations
from collections import deque               # Data container for live incoming readings
import csv                                   # Save data as spreadsheet-compatible files
import os                                    # File and folder path operations
from tkinter import filedialog              # Open the "Save As" window

import matplotlib                            # Plotting library
matplotlib.use("TkAgg")                     # Tell matplotlib to draw inside a Tkinter window
import matplotlib.pyplot as plt             # Used to create the figure and axes
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # Joins matplotlib graph into Tkinter window

# ----------------------------------------------------------------------------
# 1. CONSTANTS
# -----------------------------------------------------------------------------

# Font definitions
FONT_LABEL  = ("Courier New", 9,  "bold")   # Small label above each card
FONT_VALUE  = ("Courier New", 18, "bold")   # Big number inside each card
FONT_UNIT   = ("Courier New", 9)            # Unit text beside the big number
FONT_STATUS = ("Courier New", 10, "bold")   # Status pill text (IDLE / RUNNING / BROKEN)
FONT_BTN    = ("Courier New", 9,  "bold")   # All toolbar buttons

# Colour palette 
COLOR_BG      = "#F7F7F5"   # Page background (warm off-white)
COLOR_CARD    = "#FFFFFF"   # Metric card background (pure white)
COLOR_BORDER  = "#D0D0CC"   # Card and separator borders (light grey)
COLOR_ACCENT  = "#1A56DB"   # Primary blue —  START button and main plot line
COLOR_PEAK    = "#D93025"   # Red —  peak markers and STOP button
COLOR_TEXT    = "#000000"   # Main text colour 
COLOR_SUBTEXT = "#000000"   # Secondary text — units, labels (mid grey)
COLOR_IDLE    = "#888888"   # Status pill colour when idle
COLOR_RUNNING = "#1A56DB"   # Status pill colour when running
COLOR_BROKEN  = "#D93025"   # Status pill colour when fracture detected

BREAK_DROP_FRACTION = 0.30  # 30% drop needed
ELASTIC_WINDOW = 0.005     

# Speed-to-mmPerStep lookup 
# mmPerStep = threadPitch / (stepsPerRev * microstepFactor)
MM_PER_STEP = {
    10:  1.5 / (200 * 16),   # 0.00046875 mm — microstep factor 16
    20:  1.5 / (200 * 16),   # 0.00046875 mm — microstep factor 16
    50:  1.5 / (200 * 16),   # 0.00046875 mm — microstep factor 16
    100: 1.5 / (200 * 8),    # 0.00093750 mm — microstep factor 8
    200: 1.5 / (200 * 4),    # 0.00187500 mm — microstep factor 4
}

# -----------------------------------------------------------------
# 2. METRIC CARD WIDGET
#------------------------------------------------------------------

class MetricCard(ttk.Frame):  

    def __init__(self, parent, label, unit, width=160, **kw):
        # parent = the frame this card lives inside
        # label  = text shown on the card 
        # width  =  in pixels

        super().__init__(parent, style="Card.TFrame", **kw)  # Build the frame itself
        self.configure(width=width)                           # Set the card width

        # Label row — sits at the top of the card
        ttk.Label(self, text=label, style="CardLabel.TLabel").pack(anchor="w", padx=10, pady=(8, 0))
        # anchor="w" = align text to the left (West)
        # padx=10    = 10px space on left and right
        # pady=(8,0) = 8px space above, 0px below

        # Value row — sits below the label
        val_frame = ttk.Frame(self, style="Card.TFrame")
        val_frame.pack(anchor="w", padx=10, pady=(0, 8))
        # pady=(0,8) = 0px above, 8px below

        # The big number — stored in a StringVar so we can update it later
        self._val_var = tk.StringVar(value="—")              # "—" means no data yet
        ttk.Label(val_frame, textvariable=self._val_var,
                  style="CardValue.TLabel").pack(side="left")  # Number on the left

        # The unit text beside the number
        ttk.Label(val_frame, text=f"  {unit}",
                  style="CardUnit.TLabel").pack(side="left", anchor="s", pady=(0, 3))
        # anchor="s" = align to the bottom so it sits at the baseline of the number

    def set(self, value):
        # Called from outside to update the displayed number
        # Example: self.card_force.set("123.45")
        self._val_var.set(value)

# ------------------------------------------------------------------
# 3. MAIN APPLICATION CLASS
# ------------------------------------------------------------------

class TensileGUI:
    def __init__(self, root):       # root = the main Tkinter window passed in from the bottom of the file
        self.root = root            # Store the window so every method in the class can use it
        self.root.title("Mini Tensile Tester")
        self.root.configure(bg=COLOR_BG)  # Set the window background colour

        self.ser     = None # Serial object — None means not yet connected
        self.running = False  # True while a test is running, False otherwise
        self.force_offset = 0.0  # Force offset applied after tare to ensure readings start at 0
        self.taring = False  # True while waiting for Arduino to confirm TARE

        self.current_speed     = 50               # Default speed mm/min — matches Arduino default
        self.current_mmPerStep = MM_PER_STEP[50]  # mmPerStep matching default speed
        #Input validation 
        vcmd = (self.root.register(self._validate_positive), "%P") # entry box validation

        # Input variables (text entry boxes) 
        self.L0_var = tk.StringVar(value="")   # Gauge length L0 in mm
        self.W_var  = tk.StringVar(value="")   # Width in mm
        self.T_var  = tk.StringVar(value="")   # Thickness in mm
        self.A_var  = tk.StringVar(value="")   # Area mm² — auto calculated, read-only
        
        # Graph selector variable 
        self.plot_mode_var = tk.StringVar(value="Force vs Displacement") # default graph  # Default graph shown at startup

        # Status bar variables 
        self.status_var    = tk.StringVar(value="Searching for Arduino…")  # Bottom status message
        self.machine_state = tk.StringVar(value="IDLE")                    # Pill badge text

        # Data buffers 
        # deque automatically deletes old values at maxlen
        self.max_points  = 20000       # Maximum points kept in memory
        self.t_s  = deque(maxlen=self.max_points)  # Time in seconds
        self.force = deque(maxlen=self.max_points)  # Force in N
        self.disp  = deque(maxlen=self.max_points)  # Displacement in mm
        self.stress = deque(maxlen=self.max_points)  # Stress in MPa  (force / area)
        self.strain = deque(maxlen=self.max_points)  # Strain (disp  / L0)
        self.force_window = deque(maxlen=40) # Last 40 force readings  (for averaging)
        self.disp_window = deque(maxlen=40) # Last 40 displacement readings

        self.t0_ms = None  # Timestamp of the very first data point — used to make time start at 0

        # Maximum values
        # These are updated every time a new data point arrives
        self.peak_force  = 0.0   # Highest force seen so far in N
        self.peak_disp   = 0.0   # Displacement at that peak force
        self.peak_stress = 0.0   # Highest stress seen so far in MPa
        self.peak_strain = 0.0   # Strain at that peak stress

        # These are only set once, when fracture is detected
        self.break_force = None  # Force at the moment of fracture (N)
        self.break_disp  = None  # Displacement at the moment of fracture (mm)

        self.youngs_mod  = None  # Young's Modulus in MPa — calculated from elastic region

        # Build the window 
        self._apply_styles()       # Set colours and fonts for all widgets
        self._build_ui(vcmd)       # Place all buttons, cards, and the graph

        # -------------------------------------------------------------
        # SPEED CONTROL
        # -------------------------------------------------------------

        def set_speed(self, speed_mmPerMin):
            """Send speed command to Arduino. Only works when test is not running."""
            if self.running:
                self.status_var.set("Cannot change speed during a test — press STOP first.")
                return
            if self.ser and self.ser.is_open:
                self.ser.write(f"SPEED_{speed_mmPerMin}\n".encode())  # Send command to Arduino
                self.current_speed     = speed_mmPerMin               # Update local speed
                self.current_mmPerStep = MM_PER_STEP[speed_mmPerMin]  # Update local mmPerStep
                self.card_speed.set(str(speed_mmPerMin))              # Update speed card display
                self._highlight_speed_button(speed_mmPerMin)          # Highlight active button
                self.status_var.set(
                    f"Speed set to {speed_mmPerMin} mm/min  "
                    f"(mmPerStep = {self.current_mmPerStep:.7f} mm)")
            else:
                self.status_var.set("Arduino not connected — cannot set speed.")

        def _highlight_speed_button(self, active_speed):
            """Make the active speed button blue, all others grey."""
            for spd, btn in self.speed_buttons.items():
                if spd == active_speed:
                    btn.configure(style="SpeedActive.TButton")  # Blue = active
                else:
                    btn.configure(style="Speed.TButton")        # Grey = inactive


        self.set_ui_running(False) # Start in the idle state

        # Lock speed buttons when running — unlock when stopped
        # Speed must not change mid-test as it would break displacement calculation
        for btn in self.speed_buttons.values():
            btn.configure(state="disabled" if running else "normal")

        self.auto_connect_arduino()# Try to find and connect to the Arduino immediately

        # Repeating loops 
        self.root.after(50,  self.read_serial)   # Read incoming serial data every 50 ms
        self.root.after(200, self.update_plot)   # Refresh the graph every 200 ms

        # call on_close() instead of just quitting
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # -------------------------------------------------------------
    # 4.  STYLES
    # ------------------------------------------------------------

    def _apply_styles(self):
        s = ttk.Style()
        s.theme_use("clam")  # "clam"  built-in ttk theme

        s.configure(".", # "." means: apply to ALL widgets as a default
                    background=COLOR_BG,
                    foreground=COLOR_TEXT,
                    font=FONT_BTN)

        # Toolbar area background
        s.configure("Toolbar.TFrame", background=COLOR_BG)

        # Metric card 
        s.configure("Card.TFrame",
                    background=COLOR_CARD,
                    relief="solid",      # Draw a solid rectangle border
                    borderwidth=1)       # 1 pixel thick

        # Text styles used inside metric cards
        s.configure("CardLabel.TLabel",      # Small label at the top
                    background=COLOR_CARD,
                    foreground=COLOR_SUBTEXT,
                    font=FONT_LABEL)

        s.configure("CardValue.TLabel",      # Big number
                    background=COLOR_CARD,
                    foreground=COLOR_TEXT,
                    font=FONT_VALUE)

        s.configure("CardUnit.TLabel",       # Unit beside the number
                    background=COLOR_CARD,
                    foreground=COLOR_SUBTEXT,
                    font=FONT_UNIT)

        # START button — solid blue
        s.configure("Accent.TButton",
                    font=FONT_BTN,
                    foreground="#FFFFFF",    # White text
                    background=COLOR_ACCENT, # Blue background
                    padding=(8, 4))
        s.map("Accent.TButton",             # Colour changes for different button states
              background=[("active",   "#1446B0"),   # Darker blue when hovered/clicked
                          ("disabled", COLOR_BORDER)],# Grey when disabled
              foreground=[("disabled", COLOR_SUBTEXT)])

        # STOP button — solid red
        s.configure("Stop.TButton",
                    font=FONT_BTN,
                    foreground="#FFFFFF",
                    background=COLOR_PEAK,
                    padding=(8, 4))
        s.map("Stop.TButton",
              background=[("active",   "#B02820"),
                          ("disabled", COLOR_BORDER)],
              foreground=[("disabled", COLOR_SUBTEXT)])

        # All other buttons — light grey
        s.configure("Plain.TButton",
                    font=FONT_BTN,
                    padding=(8, 4),
                    background="#ECECEA",
                    foreground=COLOR_TEXT)
        s.map("Plain.TButton",
              background=[("active",   "#DCDCDA"),
                          ("disabled", COLOR_BORDER)])

        # Status pill label (the IDLE / RUNNING / BROKEN badge)
        s.configure("Status.TLabel",
                    font=FONT_STATUS,
                    background=COLOR_BG,
                    foreground=COLOR_IDLE)

        # Thin vertical/horizontal divider lines between button groups
        s.configure("Sep.TSeparator", background=COLOR_BORDER)

        # Speed button styles - inactive (grey) and active (blue)
        s.configure("Speed.TButton",
                    background=COLOR_BORDER,
                    foreground=COLOR_TEXT)
        s.configure("SpeedActive.TButton",
                    background=COLOR_ACCENT,
                    foreground="#FFFFFF")


    # -----------------------------------------------------------------
    # 5. BUILD UI
    # -----------------------------------------------------------------

    def _build_ui(self, vcmd):
        # Make column 0 stretch to fill the window width
        self.root.grid_columnconfigure(0, weight=1)
        # Make row 3 (the graph) stretch vertically when the window is resized
        self.root.grid_rowconfigure(3, weight=1)

        # ROW 0: TOOLBAR
        tb = ttk.Frame(self.root, style="Toolbar.TFrame", padding=(10, 6))
        tb.grid(row=0, column=0, sticky="ew")  # sticky="ew" = stretch left to right

        # Direction buttons
        self.btn_dir_up = ttk.Button(tb, text="▲  DIR UP",
                                     style="Plain.TButton",
                                     command=lambda: self.set_dir("UP"))
        self.btn_dir_up.grid(row=0, column=1, padx=8)

        self.btn_dir_down = ttk.Button(tb, text="▼  DIR DOWN",
                                       style="Plain.TButton",
                                       command=lambda: self.set_dir("DOWN"))
        self.btn_dir_down.grid(row=0, column=2, padx=8)

        # Vertical separator line between button groups
        ttk.Separator(tb, orient="vertical",
                      style="Sep.TSeparator").grid(row=0, column=3, sticky="ns", padx=8)
        # sticky="ns" = stretch top to bottom 

        # Tare and Zero buttons
        self.btn_tare = ttk.Button(tb, text="TARE",
                                   style="Plain.TButton",
                                   command=self.do_tare)
        self.btn_tare.grid(row=0, column=4, padx=8)

        self.btn_zero_len = ttk.Button(tb, text="ZERO LEN",
                                       style="Plain.TButton",
                                       command=lambda: self.send_cmd("ZERO_LEN"))
        self.btn_zero_len.grid(row=0, column=5, padx=8)

        ttk.Separator(tb, orient="vertical",
                      style="Sep.TSeparator").grid(row=0, column=6, sticky="ns", padx=8)

        # Start and Stop buttons
        self.btn_start = ttk.Button(tb, text="▶  START",
                                    style="Accent.TButton",
                                    command=self.start_test)
        self.btn_start.grid(row=0, column=7, padx=8)

        self.btn_stop = ttk.Button(tb, text="■  STOP",
                                   style="Stop.TButton",
                                   command=self.stop_test)
        self.btn_stop.grid(row=0, column=8, padx=8)

        ttk.Separator(tb, orient="vertical",
                      style="Sep.TSeparator").grid(row=0, column=9, sticky="ns", padx=8)

        # Export and Clear buttons
        self.btn_save = ttk.Button(tb, text="EXPORT",
                                   style="Plain.TButton",
                                   command=self.save_data_and_plot)
        self.btn_save.grid(row=0, column=10, padx=8)

        self.btn_clear = ttk.Button(tb, text="CLEAR",
                                    style="Plain.TButton",
                                    command=self.clear_data)
        self.btn_clear.grid(row=0, column=11, padx=8)

        # Push the status labels to a little right
        tb.grid_columnconfigure(12, weight=2)  # Column 12 expands → pushes columns 13/14 right

        # State pill (IDLE / RUNNING / BROKEN)
        self.lbl_state = ttk.Label(tb,
                                   textvariable=self.machine_state,
                                   style="Status.TLabel")
        self.lbl_state.grid(row=0, column=13, padx=(10, 4), sticky="e")

        # Connection status (e.g. "Connected · COM3")
        ttk.Label(tb,
                  textvariable=self.status_var,
                  font=("Courier New", 8),
                  background=COLOR_BG,
                  foreground=COLOR_SUBTEXT
                  ).grid(row=0, column=14, padx=(0, 8), sticky="e")

        # ROW 1: INPUTS 
        inp = ttk.Frame(self.root, style="Toolbar.TFrame", padding=(10, 4))
        inp.grid(row=1, column=0, sticky="ew")

        # L0
        ttk.Label(inp, text="L₀ (mm)",
                background=COLOR_BG, font=FONT_LABEL,
                foreground=COLOR_SUBTEXT
                ).grid(row=0, column=0, sticky="e", padx=(0, 4))
        self.entry_L0 = ttk.Entry(inp, textvariable=self.L0_var, width=9,
                                validate="key", validatecommand=vcmd)
        self.entry_L0.grid(row=0, column=1, padx=(0, 14))

        # Width
        ttk.Label(inp, text="Width (mm)",
                background=COLOR_BG, font=FONT_LABEL,
                foreground=COLOR_SUBTEXT
                ).grid(row=0, column=2, sticky="e", padx=(0, 4))
        self.entry_W = ttk.Entry(inp, textvariable=self.W_var, width=9,
                                validate="key", validatecommand=vcmd)
        self.entry_W.grid(row=0, column=3, padx=(0, 14))
        self.W_var.trace_add("write", self._update_area)

        # Thickness
        ttk.Label(inp, text="Thickness (mm)",
                background=COLOR_BG, font=FONT_LABEL,
                foreground=COLOR_SUBTEXT
                ).grid(row=0, column=4, sticky="e", padx=(0, 4))
        self.entry_T = ttk.Entry(inp, textvariable=self.T_var, width=9,
                                validate="key", validatecommand=vcmd)
        self.entry_T.grid(row=0, column=5, padx=(0, 14))
        self.T_var.trace_add("write", self._update_area)

        # Area (read-only, auto calculated)
        ttk.Label(inp, text="Area (mm²)",
                background=COLOR_BG, font=FONT_LABEL,
                foreground=COLOR_SUBTEXT
                ).grid(row=0, column=6, sticky="e", padx=(0, 4))
        self.entry_A = ttk.Entry(inp, textvariable=self.A_var, width=9, state="readonly")
        self.entry_A.grid(row=0, column=7, padx=(0, 20))

        # Graph type dropdown
        ttk.Label(inp, text="Graph",
                  background=COLOR_BG, font=FONT_LABEL,
                  foreground=COLOR_SUBTEXT
                  ).grid(row=0, column=8, sticky="e", padx=(0, 4))

        modes = ["Force vs Time",
                 "Displacement vs Time",
                 "Force vs Displacement",
                 "Stress vs Strain"]

        self.mode_box = ttk.Combobox(inp,
                                     textvariable=self.plot_mode_var,
                                     values=modes,
                                     state="readonly",  # User can only pick from the list, not type freely
                                     width=20)
        self.mode_box.grid(row=0, column=9, padx=(0, 20))

        # ROW 2: METRIC CARDS
        # One row of six side-by-side white cards showing live numbers
        cards_outer = ttk.Frame(self.root, style="Toolbar.TFrame", padding=(10, 6))
        cards_outer.grid(row=2, column=0, sticky="new")  # sticky="new" = top of the row, full width

        # Create each card using the MetricCard class defined above
        self.card_force      = MetricCard(cards_outer, "CURRENT FORCE",        "N")
        self.card_disp       = MetricCard(cards_outer, "CURRENT DISPLACEMENT", "mm")
        self.card_peak_force = MetricCard(cards_outer, "PEAK FORCE",           "N")
        self.card_peak_disp  = MetricCard(cards_outer, "PEAK DISPLACEMENT",    "mm")
        self.card_break      = MetricCard(cards_outer, "BREAK FORCE",          "N",   width=140)
        self.card_E          = MetricCard(cards_outer, "YOUNG'S MODULUS",      "MPa", width=170)
       
        # Speed display card — shows currently selected speed
        self.card_speed = MetricCard(cards_frame, "SPEED", "mm/min")
        self.card_speed.pack(side="left", padx=4)
        self.card_speed.set(str(self.current_speed))  # Show default speed

        # Place each card into a column, side by side
        all_cards = [self.card_force, self.card_disp,
                     self.card_peak_force, self.card_peak_disp,
                     self.card_break, self.card_E]

        for i, card in enumerate(all_cards):
            card.grid(row=0, column=i, padx=(0, 8), sticky="w")

        # ROW 3: PLOT 
        # Create a matplotlib figure inside the Tkinter window
        self.fig = plt.Figure(figsize=(10, 4.5), facecolor=COLOR_CARD)
        self.ax  = self.fig.add_subplot(111)  # 1 row, 1 column, subplot #1
        # Adjust margins around the graph (left, right, top, bottom as fractions of the figure)
        self.fig.subplots_adjust(left=0.08, right=0.97, top=0.91, bottom=0.12)
        self._style_axes()  # Apply colour and grid styling to the axes

        # FigureCanvasTkAgg makes the matplotlib figure into a Tkinter widget
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().grid(row=3, column=0, padx=10, pady=(0, 10), sticky="nsew")
        # sticky="nsew" = stretch in all four directions to fill the available space

    def _update_area(self, *args):
        # Called automatically whenever width or thickness changes
        try:
            w = float(self.W_var.get())
            t = float(self.T_var.get())
            if w > 0 and t > 0:
                area = w * t
                self.A_var.set(f"{area:.4f}")
            else:
                self.A_var.set("")
        except ValueError:
            self.A_var.set("")

    def _style_axes(self):
        # Apply the engineering white style to the matplotlib axes
        self.ax.set_facecolor(COLOR_CARD)  # White plot background
        self.ax.tick_params(colors=COLOR_SUBTEXT, labelsize=8)  # Grey tick labels

        # Axis label colours
        self.ax.xaxis.label.set_color(COLOR_SUBTEXT)
        self.ax.yaxis.label.set_color(COLOR_SUBTEXT)
        self.ax.title.set_color(COLOR_TEXT)

        # Light dashed grid lines
        self.ax.grid(True, color=COLOR_BORDER, linewidth=0.6, linestyle="--")

        # Figure (the area around the plot) background
        self.fig.patch.set_facecolor(COLOR_BG)


    # --------------------------------------------------------------
    # 6. ARDUINO CONNECTION
    # --------------------------------------------------------------

    def auto_connect_arduino(self):
        # If already connected, do nothing and return True immediately
        if self.ser and self.ser.is_open:
            return True

        # Scan the computer for all connected serial devices
        ports = [p.device for p in serial.tools.list_ports.comports()]

        if not ports:
            self.status_var.set("No Arduino detected.")
            return False

        # Try each port one by one until we find the Arduino
        for port in ports:
            try:
                # Open the port at 9600 baud, wait 0.2 s for each readline
                s = serial.Serial(port, 9600, timeout=0.2)
                time.sleep(1.6)  # Wait for Arduino to reboot after connection

                try:
                    s.reset_input_buffer()  # Discard any leftover data from before
                except:
                    pass

                # Read lines from this port for up to 2 seconds
                # and look for the data header the Arduino sends at startup
                found = False
                t0 = time.time()
                while time.time() - t0 < 2.0:
                    line = s.readline().decode(errors="ignore").strip()
                    # .decode(errors="ignore") converts bytes to text, skipping invalid characters
                    # .strip() removes newline characters at the end

                    if "t_ms,force_N,disp_mm" in line:
                        found = True  # This is the Arduino we are looking for
                        break

                if found:
                    self.ser = s  # Save the open serial object for later use
                    self.status_var.set(f"Connected  ·  {port}")
                    return True
                else:
                    s.close()  # Not the Arduino — close this port and try the next one

            except:
                pass  # Port couldn't be opened — skip it

        self.status_var.set("Arduino not found. Plug in and restart.")
        return False


    def send_cmd(self, cmd):
        # Send a text command to the Arduino over serial
        # cmd = the command string

        if not self.auto_connect_arduino():
            return False  # Could not connect — do nothing

        try:
            self.ser.write((cmd + "\n").encode())
            # .encode() converts the text string into bytes (serial sends bytes, not text)
            # "\n" is a newline — the Arduino uses this to know the command has ended
            return True

        except serial.SerialException as e:
            self.status_var.set(f"Send error: {e}")
            return False

    # ---------------------------------------------------------------
    # 7. UI STATE
    # ---------------------------------------------------------------

    def set_ui_running(self, running: bool):
        # running=True - machine is active (disable START, enable STOP)
        # running=False - machine is idle   (enable START, disable STOP)

        self.running = running

        if running:
            self.btn_start .state(["disabled"])   # Grey out START
            self.btn_stop.state(["!disabled"])  # Enable STOP
            self.btn_dir_up.state(["disabled"])   # Lock direction while running
            self.btn_dir_down.state(["disabled"])
            self.machine_state.set("RUNNING")  # Update the status pill text
            self.lbl_state.configure(foreground=COLOR_RUNNING) # Blue dot
        else:
            self.btn_start   .state(["!disabled"])  # Enable START
            self.btn_stop    .state(["disabled"])   # Grey out STOP
            self.btn_dir_up  .state(["!disabled"])  # Unlock direction
            self.btn_dir_down.state(["!disabled"])

            # Show BROKEN if fracture was detected, otherwise show IDLE
            if self.break_force is not None:
                self.machine_state.set("BROKEN")
                self.lbl_state.configure(foreground=COLOR_BROKEN)       # Red
            else:
                self.machine_state.set("IDLE")
                self.lbl_state.configure(foreground=COLOR_IDLE)         # Grey


    def set_dir(self, direction):
        if self.running:
            # Prevent direction change while test is active
            self.status_var.set("Stop first to change direction.")
            return
        if direction == "UP":
            self.send_cmd("DIR UP")
            self.status_var.set("Direction = UP")
        else:
            self.send_cmd("DIR DOWN")
            self.status_var.set("Direction = DOWN")
        # Small pause to let Arduino process the direction change before next command
        self.root.after(300, lambda: None)

    def do_tare(self):
        if self.send_cmd("TARE"):
            # Capture offset NOW before clearing — window is still full of pre-tare readings
            if len(self.force_window) == self.force_window.maxlen:
                self.force_offset = sum(self.force_window) / self.force_window.maxlen
            else:
                self.force_offset = 0.0
            # Now block new readings and clear old ones
            self.taring = True
            self.force_window.clear()
            self.disp_window.clear()
            self.card_force.set("  0.00")
            self.status_var.set(f"Taring… Offset={self.force_offset:.3f}N")

    def _validate_positive(self, value):
        # Called automatically every time the user types in L0 or Area box
        # Returns True  - accept the keystroke
        # Returns False - reject it 

        if value == "":
            return True   # Empty box is allowed 

        if value.count(".") > 1:
            return False  # more than one decimal point is not allowed

        if value == ".":
            return False  # single dot alone is not accepted

        # Only allow digits and one decimal point
        allowed = "0123456789."
        if any(ch not in allowed for ch in value):
            return False

        # Final check: make sure it can actually be converted to a float
        try:
            float(value)
        except ValueError:
            return False

        return True


    # --------------------------------------------------------------
    # 8. START / STOP / CLEAR / EXPORT
    # --------------------------------------------------------------

    def start_test(self):
        mode   = self.plot_mode_var.get()
        L0_txt = self.L0_var.get().strip()
        A_txt  = self.A_var.get().strip()

        # If the user picked Stress vs Strain, we need L0 and Area first
        if mode == "Stress vs Strain":
            if L0_txt == "" or A_txt == "":
                self.status_var.set("Enter L₀ and Area for Stress-Strain.")
                return 

            try:
                L0 = float(L0_txt)
                A  = float(A_txt)
            except ValueError:
                self.status_var.set("L₀ and Area must be numbers.")
                return

            if L0 <= 0 or A <= 0:
                self.status_var.set("L₀ and Area must be > 0.")
                return

        # Send the START command to the Arduino
        if self.send_cmd("START"):
            self.set_ui_running(True)
            self.status_var.set("Test running…")

    def stop_test(self):
        # Send STOP to the Arduino and update the UI
        if self.send_cmd("STOP"):
            self.set_ui_running(False)
            self.status_var.set("Stopped.")

    def clear_data(self):
        # Wipe all stored data and reset all tracked values back to zero

        for buf in (self.t_s, self.force, self.disp,
                    self.stress, self.strain,
                    self.force_window, self.disp_window):
            buf.clear()

        self.t0_ms       = None   # Reset the time reference point
        self.peak_force  = 0.0
        self.peak_disp   = 0.0
        self.peak_stress = 0.0
        self.peak_strain = 0.0
        self.break_force = None
        self.break_disp  = None
        self.youngs_mod  = None

        # Reset all cards back to "—"
        for card in (self.card_force, self.card_disp,
                     self.card_peak_force, self.card_peak_disp,
                     self.card_break, self.card_E):
            card.set("—")

        # Reset the status pill to IDLE
        self.machine_state.set("IDLE")
        self.lbl_state.configure(foreground=COLOR_IDLE)
        self.status_var.set("Cleared.")

    def save_data_and_plot(self):
        # Export the collected data as a .csv file and the current graph as a .png file

        if not self.t_s:
            self.status_var.set("No data to save.")
            return

        # Open a "Save As" dialog for the user to choose the file location and name
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export data")

        if not path:
            self.status_var.set("Export cancelled.")
            return

        try:
            base, _ = os.path.splitext(path)  # Remove the extension to build both file names

            # Write the CSV file
            with open(base + ".csv", "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Time (s)", "Force (N)", "Displacement (mm)",
                                 "Strain", "Stress (MPa)"])
                # zip() pairs up matching values from each list, row by row
                for row in zip(self.t_s, self.force, self.disp,
                               self.strain, self.stress):
                    writer.writerow(row)

            # Save the current graph as a PNG image
            self.fig.savefig(base + ".png", dpi=300, bbox_inches="tight")
            # dpi=300        - high resolution suitable for reports
            # bbox_inches="tight" → crop whitespace around the graph

            self.status_var.set(f"Saved  ·  {os.path.basename(base)}.csv / .png")

        except Exception as e:
            self.status_var.set(f"Save error: {e}")

    # -----------------Speed selector buttons -------------------------
    # Separator to visually separate speed buttons from control buttons
    ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

    ttk.Label(toolbar,
            text="SPEED (mm/min):",
            background=COLOR_BG,
            font=FONT_BTN).pack(side="left", padx=(0, 4))

    # Create one button per speed — stored in dict for later enable/disable
    self.speed_buttons = {}
    for spd in [10, 20, 50, 100, 200]:
        btn = ttk.Button(
            toolbar,
            text=str(spd),
            style="Speed.TButton",
            command=lambda s=spd: self.set_speed(s)  # lambda captures each speed value
        )
        btn.pack(side="left", padx=2)
        self.speed_buttons[spd] = btn

    # Highlight the default speed button on startup
    self._highlight_speed_button(self.current_speed)        


    # -----------------------------------------------------------------
    # 9. READ SERIAL
    # -----------------------------------------------------------------

    def read_serial(self):
        if self.ser and self.ser.is_open:   # Only proceed if connected
            try:
                # Process every line that has arrived since last read serial()
                while self.ser.in_waiting:  # in_waiting = number of bytes waiting to be read
                    raw = self.ser.readline().decode(errors="ignore").strip()

                    if not raw:
                        continue  # Skip empty lines

                    # Skip non-data lines from the Arduino
                    if raw.startswith(("OK", "BOOT")):
                        if raw == "OK TARE":
                            self.taring = False
                            # Offset already captured in do_tare — just clear and reset
                            self.force_window.clear()
                            self.disp_window.clear()
                            self.card_force.set("  0.00")
                            self.status_var.set(f"Tare done. Offset={self.force_offset:.3f}N")

                    if raw == "ERR LIMIT":
                        continue  # Limit removed — ignore any stale messages
                    if raw.startswith("ERR"):
                        self.status_var.set(raw)
                        continue

                    if raw.lower().startswith("t_ms"):
                        continue  # Skip the CSV header line the Arduino sends at boot

                    # Split the line into its three values: time, force, displacement
                    parts = raw.split(",")
                    if len(parts) != 3:
                        continue  

                    # Convert each part from text to a number
                    try:
                        t_ms   = int(float(parts[0]))  # Time in milliseconds
                        forceN = float(parts[1])        # Force in Newtons
                        dispMM = float(parts[2])        # Displacement in mm
                    except:
                        continue  # Conversion failed — skip this line

                    if dispMM < -500.0:
                        continue

                    # Set the time reference on the very first data point
                    # so that the time axis always starts at 0 s
                    if self.t0_ms is None:
                        self.t0_ms = t_ms
                    t_sec = (t_ms - self.t0_ms) / 1000.0  # Convert ms → s

                    # Ignore all readings while Arduino is still taring
                    if self.taring:
                        continue
                    # Spike filter to ignore readings more than 3 times the current average
                    if len(self.force_window) == self.force_window.maxlen:
                        current_avg = sum(self.force_window) / self.force_window.maxlen
                        if current_avg > 0.5 and (forceN - self.force_offset) > current_avg * 3:
                            continue  # Skip this spike reading
                    self.force_window.append(forceN - self.force_offset)
                    self.disp_window .append(dispMM)

                    # Always compute live average for card display
                    if len(self.force_window) == self.force_window.maxlen:
                        avg_f = sum(self.force_window) / self.force_window.maxlen
                        avg_d = sum(self.disp_window)  / self.disp_window.maxlen

                        # Always update the live force/displacement cards
                        self.card_force.set(f"{avg_f:7.2f}")
                        self.card_disp.set(f"{avg_d:7.3f}")

                        # Only store and record data while test is running
                        # Note: card_force and card_disp still update above
                        # so live readings are always visible even when stopped
                        if not self.running:
                            continue  # Skip data storage but keep processing buffer

                        # Store the averaged values in the main data buffers
                        self.t_s  .append(t_sec)
                        self.force.append(avg_f)
                        self.disp .append(avg_d)

                        # ------ Stress and Strain calculation -----------
                        # Only possible if the user has entered L0 and Area
                        try:
                            L0_txt = self.L0_var.get().strip()
                            A_txt  = self.A_var .get().strip()

                            if L0_txt and A_txt:
                                L0 = float(L0_txt)
                                A  = float(A_txt)

                                if L0 > 0 and A > 0:
                                    self.strain.append(avg_d / L0)
                                    self.stress.append(avg_f / A)
                                else:
                                    self.strain.append(0.0)
                                    self.stress.append(0.0)
                            else:
                                self.strain.append(0.0)
                                self.stress.append(0.0)
                        except:
                            self.strain.append(0.0)
                            self.stress.append(0.0)

                        # -------- Update peak values -------
                        # If this reading is higher than anything we have seen before, store it
                        if avg_f > self.peak_force:  # finds largest positive value — correct after sign fix
                            self.peak_force = avg_f
                            self.peak_disp  = avg_d   # Also save the displacement at peak force

                        if self.stress and self.stress[-1] > self.peak_stress:
                            self.peak_stress = self.stress[-1]
                            self.peak_strain = self.strain[-1]

                        # ---------- Breaking point detection --------
                        # Triggered once, when the force falls more than BREAK_DROP_FRACTION
                        if (self.break_force is None
                                and self.peak_force > 2.0
                                and avg_d > 2.0
                                and avg_f < self.peak_force * (1 - BREAK_DROP_FRACTION)):
                            
                            self.break_force = avg_f  # Record the force at fracture
                            self.break_disp  = avg_d  # Record the displacement at fracture
                            self.card_break.set(f"{self.break_force:7.2f}")

                            # Automatically stop the test
                            if self.running:
                                self.send_cmd("STOP")
                                self.set_ui_running(False)
                                self.status_var.set("Fracture detected - test stopped")

                        # -------- Young's Modulus -----
                        # Re-calculate the modulus every time a new point arrives
                        self._update_youngs_modulus()

                        # ------- Update the metric cards -------
                        self.card_peak_force.set(f"{self.peak_force:7.2f}")
                        self.card_peak_disp.set(f"{self.peak_disp:7.3f}")

                        if self.break_force is not None:
                            self.card_break.set(f"{self.break_force:7.2f}")

                        if self.youngs_mod is not None:
                            self.card_E.set(f"{self.youngs_mod:,.0f}")

            except Exception as e:
                self.status_var.set(f"Read error: {e}")
                # Reset the serial object so a broken connection is detected
                # and auto_connect_arduino() can try to reconnect on the next cycle
                self.ser = None
        # Schedule this function to run again in 50 ms
        self.root.after(50, self.read_serial)

    # -----------------------------------------------------------------
    # 10. YOUNG'S MODULUS CALCULATION
    #
    #  Young's Modulus (E) = Stress / Strain   in the elastic region
    #  Formula:  E = Σ(strain × stress) / Σ(strain²)
    # ----------------------------------------------------------------

    def _update_youngs_modulus(self):
        if not self.strain or not self.stress:
            return   # No data yet — nothing to calculate

        eps = list(self.strain)  # All strain values
        sig = list(self.stress)  # Matching stress values

        # Keep only the points that fall inside the elastic region
        # (strain between 0 and ELASTIC_WINDOW, and stress must be positive)
        xs = [e for e, s in zip(eps, sig) if 0 < e <= ELASTIC_WINDOW and s > 0]
        ys = [s for e, s in zip(eps, sig) if 0 < e <= ELASTIC_WINDOW and s > 0]

        if len(xs) < 10:
            return   # Need at least 10 points for a reliable fit

        # Least-squares slope through the origin:
        # E = Σ(x·y) / Σ(x²)
        sum_xy = sum(x * y for x, y in zip(xs, ys))
        sum_xx = sum(x * x for x in xs)

        if sum_xx == 0:
            return   # Avoid division by zero

        self.youngs_mod = sum_xy / sum_xx   # Result is in MPa

    # -------------------------------------------------------------
    # 11. PLOT UPDATE
    # ---------------------------------------------------------------

    def update_plot(self):
        mode = self.plot_mode_var.get()

        # Clear the axes completely when the user switches between graph types
        self.ax.cla()
        self._style_axes()  # Re-apply grid and colour styling after clearing

        # Select which data to plot based on the chosen graph mode
        if mode == "Force vs Time":
            x, y   = list(self.t_s),   list(self.force)
            xl, yl = "Time (s)",        "Force (N)"

        elif mode == "Displacement vs Time":
            x, y   = list(self.t_s),   list(self.disp)
            xl, yl = "Time (s)",        "Displacement (mm)"

        elif mode == "Force vs Displacement":
            x, y   = list(self.disp),  list(self.force)
            xl, yl = "Displacement (mm)", "Force (N)"

        elif mode == "Stress vs Strain":
            x, y   = list(self.strain), list(self.stress)
            xl, yl = "Strain  (ΔL / L₀)", "Stress (MPa)"

        else:
            x, y, xl, yl = [], [], "", ""  # Fallback — should never happen

        # Apply axis labels and title
        self.ax.set_xlabel(xl, fontsize=9)
        self.ax.set_ylabel(yl, fontsize=9)
        self.ax.set_title(mode, fontsize=10, fontweight="bold", pad=8)

        # Draw the main data curve in blue
        if x and y:
            self.ax.plot(x, y, color=COLOR_ACCENT, linewidth=1.4, zorder=3)
            # zorder=3 → draw this line on top of the grid (zorder=2) but below annotations

        # ------ Peak marker ----------
        # A red dashed vertical line + arrow annotation at the peak point
        if self.peak_force > 0:  # correct after sign fix

            # Determine the x-position of the peak in the current graph mode
            if mode == "Force vs Displacement":
                px, py = self.peak_disp, self.peak_force

            elif mode == "Force vs Time" and self.t_s:
                fi  = list(self.force)  # All force values
                idx = fi.index(max(fi)) if fi else None # Index of the maximum
                px  = list(self.t_s)[idx] if idx is not None else None # Find the largest value
                py  = self.peak_force

            elif mode == "Stress vs Strain" and self.peak_stress > 0:
                px, py = self.peak_strain, self.peak_stress

            else:
                px, py = None, None  # Mode doesn't support a peak marker

            if px is not None:
                # Draw the vertical dashed line at the peak x-position
                self.ax.axvline(px, color=COLOR_PEAK, linewidth=0.8,
                                linestyle="--", alpha=0.7, zorder=2)

                # Extract just the unit from the y-axis label for the annotation text
                # e.g. "Force (N)" → "N"
                unit_text = yl.split("(")[-1].rstrip(")")

                # Draw the arrow + label
                self.ax.annotate(
                    f"Peak\n{py:.2f} {unit_text}",  # Text shown beside the arrow
                    xy=(px, py),                    # Arrow points here (the peak point)
                    xytext=(12, -18),               # Label is offset 12px right, 18px down
                    textcoords="offset points",     # Offset is in screen pixels
                    fontsize=7.5,
                    color=COLOR_PEAK,
                    arrowprops=dict(arrowstyle="->",
                                   color=COLOR_PEAK,
                                   lw=0.8),
                    zorder=5  # Draw on top of everything else
                )

        #  Breaking point marker 
        if self.break_force is not None:

            # Only show the fracture line on modes that have a meaningful x-position for it
            if mode == "Force vs Displacement":
                bx = self.break_disp  # x = displacement at fracture

            elif mode == "Stress vs Strain":
                try:
                    L0 = float(self.L0_var.get())
                    bx = self.break_disp / L0  # x = strain at fracture
                except:
                    bx = None

            else:
                bx = None  # Skip fracture line for time-based graphs

            if bx is not None:
                # Draw the dotted orange vertical line
                self.ax.axvline(bx, color="#FF7A00", linewidth=1.0,
                                linestyle=":", alpha=0.85, zorder=2)

                # Place the "Breaking point" label vertically along the line
                # Position it near the bottom of the plot (5% of y range)
                y_bottom = self.ax.get_ylim()[1] * 0.05 if self.ax.get_ylim()[1] != 0 else 0

                self.ax.annotate(
                    "Breaking Point",
                    xy=(bx, y_bottom),
                    fontsize=7.5,
                    color="#FF7A00",
                    rotation=90,       # Rotate the text 90° so it runs vertically
                    va="bottom",       # Align to bottom of the text box
                    ha="right",        # Align to right of the text box
                    zorder=5
                )

        # Recalculate axis limits to fit all current data
        self.ax.relim()
        self.ax.autoscale_view()

        # Redraw the canvas
        self.canvas.draw_idle()

        # Schedule this function to run again in 200 ms
        self.root.after(200, self.update_plot)

    # -------------------------------------------------------------
    # 12. CLOSE
    # --------------------------------------------------------------

    def on_close(self):
        try:
            if self.ser and self.ser.is_open:
                self.ser.write(b"STOP\n")  # b"..." = bytes literal (no .encode() needed)
                time.sleep(0.1)            # Give Arduino time to process the command
        except:
            pass  # If sending fails, continue to close anyway

        try:
            if self.ser and self.ser.is_open:
                self.ser.close()           # Close the serial port cleanly
        except:
            pass

        self.root.destroy()  # Close the Tkinter window and end the program

# --------------------------------------------------------------
#  ENTRY POINT
# ---------------------------------------------------------------

if __name__ == "__main__":
    root = tk.Tk()           # Create the main application window
    root.state("zoomed")     # Start maximised (full screen)
    app = TensileGUI(root)   # Build the entire GUI by creating a TensileGUI object
    root.mainloop()          # Tkinter — runs until the window is closed