# 🔬 MiniTensileMachine

A low-cost, open-source **miniature tensile testing machine** built as a Final Year Research project. The system uses an Arduino-controlled stepper motor to apply tensile load to a specimen, while a Python GUI provides real-time data acquisition, live plotting, and materials analysis.

---

## 📌 Project Overview

Traditional tensile testing machines are expensive and inaccessible for small research labs or educational use. This project demonstrates that accurate tensile testing can be achieved with affordable off-the-shelf components and custom software, making it suitable for polymer films, paper, textiles, and other low-strength materials.

---

## 🛠️ Hardware Components

| Component | Role |
|---|---|
| Arduino Uno | Microcontroller — reads sensors and drives the motor |
| A4988 Stepper Driver | Controls the NEMA stepper motor for precise crosshead movement |
| HX711 Load Cell Amplifier | Amplifies the load cell signal for Arduino |
| Load Cell (strain gauge) | Measures applied force in Newtons |
| NEMA Stepper Motor | Drives the crosshead (UP / DOWN) |
| Custom PCB | Integrates all components cleanly |

---

## 💻 Software

### Python GUI — `tensile_tester_guiV5.py`

The main application (`Python application/tensile_tester_guiV5.py`) is a full-featured desktop GUI built with **Tkinter** and **Matplotlib**.

#### Features

- 🔌 **Auto-connect to Arduino** — detects the correct COM port automatically on startup
- ▶️ **Start / Stop test control** — sends commands to Arduino over serial
- ↕️ **Motor direction control** — UP / DOWN before a test begins
- ⚖️ **Tare & Zero Length** — zero the load cell and displacement reference
- 📊 **Live real-time plotting** with 4 selectable graph modes:
  - Force vs Time
  - Displacement vs Time
  - Force vs Displacement
  - Stress vs Strain
- 🗃️ **Six live metric cards** — Current Force, Current Displacement, Peak Force, Peak Displacement, Break Force, Young's Modulus
- 🧮 **Automatic calculations**:
  - Cross-sectional area (Width × Thickness)
  - Engineering stress (Force / Area)
  - Engineering strain (Displacement / L₀)
  - Young's Modulus (least-squares fit over elastic region)
- 💥 **Fracture detection** — automatically stops the test when force drops >20% from peak
- 📁 **Export** — saves data as `.csv` and the current graph as a high-res `.png` into `results/`
- 🔄 **40-point moving average** — smooths noisy sensor readings in real time

---

## 📂 Project Structure

```
MiniTensileMachine/
│
├── Python application/
│   └── tensile_tester_guiV5.py   # Main Python GUI application
│
├── Arduino codes/                 # Arduino firmware (serial data + motor control)
│
├── PCB/                           # PCB design files
│
├── results/                       # Exported test data (CSV + PNG plots)
│   └── .gitkeep                   # Keeps the folder tracked; contents are git-ignored
│
├── requirements.txt               # Python dependencies
└── README.md
```

---

## ⚙️ Setup & Usage

### Requirements

```bash
pip install -r requirements.txt
```

> Python 3.8+ and `tkinter` (included with standard Python on Windows) are required.

### Running the Application

1. Upload the Arduino firmware from `Arduino codes/` to the Arduino Uno.
2. Connect the Arduino via USB.
3. Run the GUI:

```bash
cd "Python application"
python tensile_tester_guiV5.py
```

4. The app will auto-detect the Arduino on the correct COM port.

### Performing a Test

1. (Optional) Enter **L₀**, **Width**, and **Thickness** for stress/strain calculations.
2. Select the desired **graph type** from the dropdown.
3. Click **TARE** to zero the load cell and **ZERO LEN** to zero the displacement.
4. Set the motor direction (**DIR UP** to pull the specimen).
5. Click **▶ START** to begin the test.
6. The machine will automatically stop when fracture is detected.
7. Click **EXPORT** to save the data and plot — the dialog opens in `results/` by default.

---

## 📈 Measured Outputs

| Parameter | Unit | Description |
|---|---|---|
| Force | N | Applied tensile load |
| Displacement | mm | Crosshead travel distance |
| Stress | MPa | Force / Cross-sectional area |
| Strain | — | Displacement / Gauge length (L₀) |
| Young's Modulus | MPa | Slope of the elastic region (E = σ/ε) |
| Peak Force | N | Maximum force reached during the test |
| Break Force | N | Force at the moment of specimen fracture |

---

## 📡 Serial Communication Protocol

The Arduino sends comma-separated data lines at 9600 baud:

```
t_ms,force_N,disp_mm       ← header sent at boot
1234,5.62,0.031             ← data line (time ms, force N, displacement mm)
```

The GUI sends text commands to the Arduino:

| Command | Action |
|---|---|
| `START` | Begin test (motor ON, data streaming) |
| `STOP` | Stop motor |
| `DIR UP` | Set motor direction to UP (tension) |
| `DIR DOWN` | Set motor direction to DOWN |
| `TARE` | Zero the load cell |
| `ZERO_LEN` | Zero the displacement sensor |

---

## 📸 Screenshots

> Exported test plots and data are saved to the `results/` folder.

---

## 👨‍🔬 Author

Final Year Research Project — Department of Engineering  
Built with Arduino, Python, and custom PCB hardware.
