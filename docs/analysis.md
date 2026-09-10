# Detailed Analysis

Wire crimp forming of a 19-strand copper conductor into a copper-alloy ferrule,
solved with LS-DYNA SMP R16.1. All numerical values in this document are taken
from the solver output committed in [`../results/`](../results/).

---

## 1. Objective

The objective of the simulation is to study the mechanical forming behaviour
of a multi-strand wire during crimping. The 19-strand copper conductor is
compressed into a copper-alloy ferrule, producing permanent plastic
deformation and mechanical contact between the conductor and ferrule.

The process is therefore a nonlinear forming problem involving large
deformation, plasticity, contact and friction rather than a simple structural
strength calculation.

This project was developed as a self-directed reproduction of a published
wire-crimping simulation originally developed in Abaqus/Explicit. The model
was rebuilt independently in LS-DYNA to study explicit quasi-static forming
and the associated numerical solution controls.

The analysis focuses on the forming force, energy balance, quasi-static
behaviour and numerical solution quality.

---

## 2. Model

### Geometry and discretisation

| | |
|---|---|
| Nodes | 85,405 |
| Solid elements | 67,375, ELFORM 1 (reduced integration) |
| Shell elements | 1,452 rigid — 860 punch, 592 anvil |
| Parts | 19 deformable strands + 1 deformable ferrule + 2 rigid tools |
| Ferrule | 3.30 × 3.25 × 5.44 mm, wall 0.245 mm across 4 elements |
| Strand | Ø 0.286 mm, 19-strand bundle Ø 1.35 mm |
| Ferrule element count | 4,888 — 7.3 % of the solids |
| Physical mass | 1.241 g |
| Units | mm – tonne – s (force N, stress MPa, energy mJ) |

The ferrule wall is represented by four solid elements through its thickness.
This provides multiple elements across the wall while keeping the model
computationally manageable. The 19 individual strands are modelled as separate
deformable bodies, allowing the strands to deform and rearrange during
crimping.

The strand bundle is initially packed inside the ferrule, while the rigid
punch and anvil define the forming tools. The ferrule contains 4,888 of the
67,375 solid elements. Although it represents only 7.3 % of the solid
elements, the ferrule undergoes substantial plastic deformation and carries
a large portion of the deformation work during crimping.

### Materials

`*MAT_PIECEWISE_LINEAR_PLASTICITY` (MAT_024) with tabulated true-stress /
plastic-strain curves supplied through `LCSS`.

| | E | ν | σ_y | ρ |
|---|---|---|---|---|
| Strand | 117 GPa | 0.35 | 241.5 MPa | 8.5e-9 t/mm³ |
| Ferrule | 112 GPa | 0.34 | 391 MPa | 8.5e-9 t/mm³ |

Both the conductor strands and the ferrule are represented using copper-based
material data. The ferrule has the higher initial yield stress (391 MPa
compared with 241.5 MPa for the strands), representing the harder material in
the crimping system.

The material behaviour is defined using tabulated true-stress / plastic-strain
curves through `LCSS`. The material curves were taken from the reference model
and were not independently measured as part of this project.

The tabulated curves therefore define the plastic response used in the
simulation rather than providing an experimental validation of the material
behaviour.

### Contact

Five interfaces, segment-based penalty formulation (`SOFT = 1`,
`SOFSCL = 0.1`, `DEPTH = 5`), initial-penetration tracking `IGNORE = 2`.
Rigid tools carry a 0.1 mm shell thickness with a contact-thickness override
`SBST = 0.05`.

| ID | Interface | Formulation | µ | CPU share |
|---|---|---|---|---|
| 1 | Ferrule → anvil | `AUTOMATIC_SURFACE_TO_SURFACE` | 0.30 | 0.99 % |
| 2 | Ferrule → punch | `AUTOMATIC_SURFACE_TO_SURFACE` | 0.15 | 0.96 % |
| 3 | Strand self-contact | `AUTOMATIC_GENERAL` | 0.15 | 22.40 % |
| 4 | Ferrule self-contact | `AUTOMATIC_GENERAL` | 0.30 | 1.02 % |
| 5 | Strands → ferrule | `AUTOMATIC_SURFACE_TO_SURFACE` | 0.15 | 2.85 % |

The crimping process involves several contact interactions. Contact is
defined between the strands themselves, between the strands and the ferrule,
and between the deformable components and the rigid forming tools.

Penalty-based segment contact with `SOFT = 1` is used. Friction is included
with coefficients between 0.15 and 0.30 depending on the contacting surfaces.

Strand self-contact is particularly important because the individual strands
move relative to each other as the conductor is compressed. This contact is
also a significant contributor to the computational cost of the simulation.

The final model uses `AUTOMATIC_GENERAL` for strand self-contact.
`AUTOMATIC_SINGLE_SURFACE` could be investigated as an alternative
formulation to reduce computational cost.

### Loading and boundary conditions

Punch stroke 6.88 mm in −Y over 0.122333 s, prescribed displacement on a
rigid body. Smooth-step profile in four phases, zero velocity **and** zero
acceleration at every breakpoint:

| Phase | Ends at | Cumulative stroke |
|---|---|---|
| Approach | 0.018 s | 0.90 mm |
| Closing | 0.031 s | 4.75 mm |
| Folding | 0.091 s | 6.25 mm |
| Final compaction | 0.122333 s | 6.88 mm |

Peak punch speed 562.5 mm/s. Strand end nodes fixed in x/y/z; anvil fully
constrained; punch free in Y only (`CON1 = 6`, `CON2 = 7`).

The forming motion is prescribed through the punch displacement. The punch
moves through a total stroke of 6.88 mm over 0.122333 s.

A smooth-step displacement history is used with four velocity phases. This
avoids an abrupt change in the applied velocity and provides a controlled
transition into and out of the forming motion.

The anvil is fixed while the punch provides the forming displacement. The
initial position of the conductor and ferrule leaves a clearance between the
punch and the ferrule, which explains the initial force-free portion of the
force-stroke curve.

The reported final state corresponds to the end of the forming process before
any separate springback or tool-release analysis.

---

## 3. Solution strategy

| | |
|---|---|
| Solver | LS-DYNA SMP R16.1, double precision, 4 threads |
| Time step | `DT2MS = −3.0e-7`, `TSSFAC = 0.9` → Δt = 2.7e-7 s, constant for 453,086 cycles |
| Added mass | 22,936 % at cycle 1 → 26,395 % at termination (mass factor 230 → 265) |
| Hourglass | `*CONTROL_HOURGLASS` IHQ 6, QH 0.1 |
| Accuracy | `*CONTROL_ACCURACY` OSU 1, INN 4 |
| Bulk viscosity | Q1 1.2, Q2 0.06 |

The analysis is solved with the explicit time integration scheme, but the
forming process is intended to represent quasi-static behaviour. The loading
time is therefore chosen so that inertial effects remain small relative to
the deformation energy.

Mass scaling is applied using `DT2MS = −3.0e-7 s` to increase the stable
timestep. The resulting timestep is approximately 2.7e-7 s and remains
constant throughout the 453,086 cycles.

The effect of mass scaling is assessed using the kinetic-to-internal-energy
ratio rather than assuming that the scaled model is automatically
quasi-static. The maximum KE/IE ratio is approximately 1.92 %, while the
final value is approximately 0.003 %.

This provides an a-posteriori check that the reported forming response is not
dominated by inertial effects. However, the aggressive mass scaling means
that inertia-dependent quantities should not be interpreted from this model.

---

## 4. Verification

An explicit solver never fails to converge — it always produces a result, and
a wrong result looks like a right one. Everything in this section is the check
that the solver cannot do for itself.

### Did the run finish cleanly

The final simulation reached the intended end time and terminated normally
after 453,086 cycles. The timestep remained constant at approximately
2.7e-7 s throughout the run, and no elements were eroded.

The total wall-clock time was approximately 6 h 48 min on 4 SMP threads.

### Energy balance

| Quantity | Value | Share of total |
|---|---|---|
| Internal | 1429.2 mJ | 67.7 % |
| Sliding interface | 527.2 mJ | 25.0 % |
| Hourglass | 156.2 mJ | 7.4 % |
| Kinetic | 0.0412 mJ | 0.002 % |
| **Total** | **2112.6 mJ** | 100 % |
| External work | 2113.8 mJ | — |

Sum check: 1429.2 + 527.2 + 156.2 + 0.04 = 2112.6 mJ exactly.
**Energy ratio 0.999426**, inside 0.999426 – 1.00027 for the entire run.
Friction accounts for 478.2 of the 527.2 mJ of sliding energy (91 %).

The energy balance is used as a global check of the numerical solution. The
total energy is compared with the external work throughout the simulation
rather than considering internal energy alone.

The total-to-external-work ratio remains very close to unity, ranging from
0.999426 to 1.00027 over the complete run. This indicates that the global
energy balance is maintained throughout the forming process.

The energy components are plotted separately because they provide different
information about the solution. Internal energy represents the deformation
work, sliding-interface energy represents frictional and contact work,
hourglass energy indicates energy associated with hourglass control, and
kinetic energy is used to assess inertial effects.

### Quasi-static check

KE / IE = **0.0029 %** at termination, maximum **1.92 %** at t = 0.024 s
during the fast closing phase — under the 5 % rule of thumb throughout.

The explicit simulation is intended to represent a quasi-static forming
process. The kinetic-to-internal-energy ratio (KE/IE) is therefore monitored
throughout the simulation to assess the influence of inertia.

The ratio reaches a maximum of approximately 1.92 % and decreases to
approximately 0.003 % at the final state. The low kinetic-energy contribution
relative to the internal energy indicates that the forming response is not
dominated by inertial effects.

The quasi-static behaviour is therefore supported by the KE/IE evaluation.

### Force equilibrium

| | |
|---|---|
| Peak crimping force | 3919.5 N (punch) / 3932.3 N (anvil) at t = 0.1120 |
| Imbalance at peak | **0.33 %** |
| Imbalance at final state | 0.06 % |
| Worst imbalance above 100 N | 2.79 % |
| Anvil reaction negative anywhere | No — 62/62 samples compressive |
| Punch reaction positive anywhere | No — 62/62 samples compressive |

The punch and anvil reaction forces are compared as an internal equilibrium
check. During forming, the two tools should transmit essentially the same
reaction force in magnitude, with opposite directions.

At the peak load, the punch reaction is 3.92 kN and the anvil reaction is
3.93 kN. Their magnitudes differ by approximately 0.33 %.

This close agreement indicates that the global force transfer through the
forming system is consistent at the peak load.

### Hourglass energy

HG / IE = **10.93 %** at termination, maximum 13.20 %. Located by part:

| | Internal | Hourglass | HG / IE |
|---|---|---|---|
| Ferrule | 1112.1 mJ (78 %) | 130.2 mJ (83 %) | **11.7 %** |
| 19 strands | 317.1 mJ (22 %) | 26.0 mJ (17 %) | **8.2 %** |

The hourglass energy is monitored as an indicator of non-physical
zero-energy deformation modes in the solid elements.

The hourglass-to-internal-energy ratio reaches approximately 13.2 % during
the simulation and is approximately 10.9 % at termination. This exceeds the
commonly used 10 % guideline and is therefore identified as a numerical
limitation of the current model.

The global force response and energy balance remain consistent, but local
deformation results in regions strongly affected by hourglass deformation
should not be interpreted quantitatively. A future model improvement would
be to investigate the element formulation, mesh quality and hourglass
control in the affected regions.

---

## 5. Results

The force-stroke response shows three main stages of the forming process.
During the first approximately 4.5 mm of punch stroke, the punch closes the
initial gap and the reaction force remains very low. As the ferrule begins to
deform, the force increases as the ferrule arms are bent inward.

The force then shows a reduction associated with the bending and buckling of
the ferrule arms. As the strands become progressively compacted inside the
ferrule cavity, the forming resistance increases strongly, reaching a peak of
approximately 3.92 kN at a punch stroke of 6.75 mm. The force subsequently
relaxes as the punch decelerates towards the end of the prescribed motion.

The deformation mechanism is characterised by the ferrule arms folding inward
and over the conductor while the individual strands are progressively
compacted into the cavity. The ferrule subsequently becomes seated against
the die.

The ferrule accounts for approximately 78 % of the internal energy at the
reported final state. This is consistent with the substantial plastic
deformation required to fold the ferrule during the crimping process.

---

## 6. Model development

Three runs, one variable at a time, same mesh and materials throughout.

| | Run 1 | Run 2 | Final |
|---|---|---|---|
| Anvil die | 74 shells, AR 178:1 | 592 shells, AR 22:1 | 592 shells, AR 22:1 |
| Hourglass control | IHQ 4 / 0.03 | IHQ 6 / 0.1 | IHQ 6 / 0.1 |
| Peak force | 2558 N | 3885 N | **3920 N** |
| Imbalance at peak | 0.44 % | 0.29 % | 0.33 % |
| HG / IE | 11.26 % | 11.74 % | **10.93 %** |
| Energy ratio | 0.99991 | 0.99944 | 0.99943 |
| Ferrule→anvil interface energy | 73.1 mJ | 15.2 mJ | **17.1 mJ** |
| Runtime | 7 h 41 | 15 h 36 | 6 h 48 |

### 6.1 The die aspect ratio changed the answer by 52 %

The anvil was originally a single element across the extrusion direction:
in-plane edge 0.025 mm against a 4.43 mm element length, an aspect ratio of
**178 : 1**. Refining it 8× to 22 : 1 took ferrule→anvil contact energy — the
work stored in penetration — from **73.1 to 17.1 mJ, a 77 % reduction**, and
moved peak force from **2558 to 3920 N**.

Two independent runs with the refined die gave 3885 and 3920 N, **0.9 %
apart**, so the change is the die fix and not solver scatter.

The die geometry was refined during model development to improve the
representation of the forming contact region. The refinement changed the
predicted forming response significantly, demonstrating that the local die
discretisation has an important influence on the numerical solution.

The refined configuration reduced the penetration-related work and produced a
different peak forming force. The final die configuration was therefore
selected for the reported simulation.

The comparison is a model-development investigation rather than an
experimental validation. The purpose was to identify the influence of the
numerical representation of the die on the forming response.

### 6.2 Hourglass control was not the lever

IHQ 4 gave 11.26 %; IHQ 6 gave 11.74 % at roughly twice the solid-element
cost.

The hourglass energy was investigated because the initial solution showed a
relatively high hourglass contribution. Different numerical settings were
therefore examined during model development with the objective of reducing
non-physical hourglass deformation while maintaining a stable forming
solution.

The investigation showed that changing the hourglass control formulation
alone does not reduce the hourglass contribution in this model. With a single
integration point per element, the bending mode of a reduced-integration
element is itself the hourglass mode; the hourglass control does not remove
that deformation but applies an artificial stiffness to it. Since the ferrule
wall is bending-dominated, the hourglass contribution is governed by the
element formulation and local discretisation rather than by the choice of
hourglass control.

The final reported run still reaches approximately 13.2 % hourglass energy
relative to internal energy. This remains above the commonly used 10 %
guideline and is therefore retained as a limitation of the final model.

### 6.3 Fully integrated elements: 0.73 % hourglass, and a negative volume

A fourth run set the ferrule (PID 16, 4,888 elements) to ELFORM −1, fully
integrated, leaving the strands at ELFORM 1.

| At t = 0.107 | Internal | Hourglass | HG / IE |
|---|---|---|---|
| Ferrule (ELFORM −1) | 659.4 mJ | **0.000 mJ** | **0.00 %** |
| 19 strands (ELFORM 1) | 66.6 mJ | 5.318 mJ | 7.98 % |
| **Total** | 726.0 mJ | 5.318 mJ | **0.73 %** |

Force equilibrium 0.32 %, KE / IE 8×10⁻⁵ %. The run then **error-terminated**
at t = 0.10746 — 88 % of the stroke — with a negative volume in element
53399, a 0.09 × 0.11 × 0.15 mm element in the tightly folded arm at the free
end face.

This configuration achieved a substantially lower hourglass contribution
during the forming process. However, the simulation terminated because of a
negative element volume, and the run was therefore not used as the reported
final result.

The trade-off is the useful outcome of this investigation. A
reduced-integration element can deform into an hourglass mode, which is the
source of the inaccuracy, but that mode also acts as a relief mechanism under
severe distortion. A fully integrated element has no such mode and resists
until the element Jacobian becomes negative. Full integration is therefore
more accurate and less robust, and for a part folded to a tight radius the
robustness is the governing constraint.

---

## 7. Limitations

The current model has several numerical and physical limitations that should
be considered when interpreting the results.

The hourglass energy exceeds the commonly used 10 % guideline, reaching
approximately 13.2 % during the simulation. Therefore, local deformation and
strain results in strongly affected regions are not interpreted
quantitatively.

The applied mass scaling is also aggressive. Although the low KE/IE ratio
supports the quasi-static assumption, the increased mass means that
inertia-dependent quantities are not meaningful for this model.

Local contact penetration occurs at the punch/ferrule interface in the final
states. The global force equilibrium and energy balance remain consistent,
but local contact pressure should therefore not be interpreted quantitatively
in the affected region.

The anvil die was refined during model development from an aspect ratio of
178 : 1 to 22 : 1. The refined discretisation is used for the reported
results, but no further mesh-sensitivity study of the die was performed.

No springback or tool-release step was performed, so the unloaded final crimp
geometry is not available. In addition, no experimental validation was
performed. The results should therefore be regarded as a numerical study
rather than a validated prediction of the physical crimping process.

Finally, the simulation was performed using LS-DYNA SMP. Small numerical
differences can occur between runs depending on the parallel execution
settings.

---

## 8. Next steps

The next development step would be to reduce the hourglass contribution while
maintaining the stable forming behaviour of the current model. This could be
investigated through improved local mesh quality, an alternative element
formulation and/or different hourglass-control settings.

The contact formulation could also be reviewed, particularly the strand
self-contact, which is a significant contributor to the computational cost.

A separate springback and tool-release step would be required to determine
the unloaded final crimp geometry.

Finally, experimental validation would be required before using the model for
quantitative prediction. Useful validation data would include the forming
force-stroke curve, final crimp geometry and, where available, mechanical or
metallographic characterisation of the crimped conductor.

---

## References

[1] Dassault Systèmes, *Abaqus Example Problems Guide*, Section 2.1.10,
"Crimp forming with general contact", Abaqus/Explicit, 2016.

The Abaqus example cites the following original publications:

[2] G. Villeneuve, D. Kulkarni, P. Bastnagel, and D. Berry, "Dynamic Finite
Element Analysis Simulation of the Terminal Crimping Process," *42nd IEEE
Holm Conference*, Chicago, IL, October 1996.

[3] G. Villeneuve, P. Bastnagel, D. Berry, and C. S. Nagaraj, "Determining the
Factors Affecting Crimp Formation Using Dynamic Finite Element Analysis,"
*30th IICIT Connector and Interconnection Symposium*, Anaheim, CA,
September 1997.

[4] D. T. Berry, "Development of a Crimp Forming Simulator," *ABAQUS User's
Conference Proceedings*, pp. 125–137, 1998.
