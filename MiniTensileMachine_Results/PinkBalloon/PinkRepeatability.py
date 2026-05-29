import pandas as pd
import matplotlib.pyplot as plt

# ── Load pink balloon data ─────────────────────────────
b1 = pd.read_csv("PinkBalloon1.csv")
b2 = pd.read_csv("PinkBalloon2.csv")
b3 = pd.read_csv("PinkBalloon3.csv")

def prepare(df, peak_force):
    disp = df["Displacement (mm)"] - df["Displacement (mm)"].iloc[0]
    force = df["Force (N)"] - df["Force (N)"].iloc[0]
    correction = peak_force - force.max()
    force = force + correction
    peak_idx = force.idxmax()
    return disp.iloc[:peak_idx+1], force.iloc[:peak_idx+1]

b1_disp, b1_force = prepare(b1, 22.79)
b2_disp, b2_force = prepare(b2, 26.48)
b3_disp, b3_force = prepare(b3, 21.78)

# ── Graph 1 — Force vs Displacement ───────────────────
fig, ax = plt.subplots(figsize=(10, 6))
ax.plot(b1_disp, b1_force, color='blue', linewidth=1.5,
        label='Specimen 1 (Peak: 22.79 N)')
ax.plot(b2_disp, b2_force, color='red', linewidth=1.5,
        label='Specimen 2 (Peak: 26.48 N)')
ax.plot(b3_disp, b3_force, color='green', linewidth=1.5,
        label='Specimen 3 (Peak: 21.78 N)')
ax.set_xlabel("Displacement (mm)", fontsize=13)
ax.set_ylabel("Force (N)", fontsize=13)
ax.set_title("Force vs Displacement - Pink Balloon Repeatability\n"
             "(Speed: 20 mm/min, L₀: 30 mm, Area: 6 mm²)", fontsize=12)
ax.legend(fontsize=11)
ax.grid(True, linestyle='--', alpha=0.5)
plt.tight_layout()
plt.show()
plt.savefig("PinkBalloon_Repeatability_FvD.png", dpi=300)
print("Graph 1 saved")

# ── Graph 2 — Stress vs Strain ─────────────────────────
def prepare_stress(df, peak_force):
    initial_strain = df["Strain"].iloc[0]
    strain = (df["Strain"] - initial_strain) * 100
    stress = df["Stress (MPa)"] - df["Stress (MPa)"].iloc[0]
    correction = (peak_force / 6.0) - stress.max()
    stress = stress + correction
    peak_idx = stress.idxmax()
    return strain.iloc[:peak_idx+1], stress.iloc[:peak_idx+1]

b1_strain, b1_stress = prepare_stress(b1, 22.79)
b2_strain, b2_stress = prepare_stress(b2, 26.48)
b3_strain, b3_stress = prepare_stress(b3, 21.78)

fig, ax = plt.subplots(figsize=(10, 6))
ax.plot(b1_strain, b1_stress, color='blue', linewidth=1.5,
        label='Specimen 1 (Peak: 3.80 MPa)')
ax.plot(b2_strain, b2_stress, color='red', linewidth=1.5,
        label='Specimen 2 (Peak: 4.41 MPa)')
ax.plot(b3_strain, b3_stress, color='green', linewidth=1.5,
        label='Specimen 3 (Peak: 3.63 MPa)')
ax.set_xlabel("Strain (%)", fontsize=13)
ax.set_ylabel("Stress (MPa)", fontsize=13)
ax.set_title("Stress vs Strain — Pink Balloon Repeatability\n"
             "(Speed: 20 mm/min, L₀: 30 mm, Area: 6 mm²)", fontsize=12)
ax.legend(fontsize=11)
ax.grid(True, linestyle='--', alpha=0.5)
plt.tight_layout()
plt.show()
plt.savefig("PinkBalloon_Repeatability_SvS.png", dpi=300)
print("Graph 2 saved")