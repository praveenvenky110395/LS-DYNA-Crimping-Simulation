# Wire Crimp Forming Simulation — LS-DYNA Explicit

Crimp forming of a 19-strand copper conductor in a copper-alloy ferrule.
Explicit quasi-static analysis using LS-DYNA SMP R16.1.

## Model

67,375 solid elements · 19 deformable strands + ferrule · 2 rigid tools

Punch stroke: 6.88 mm over 0.1223 s (smooth-step, 4 velocity phases)

Material: MAT_024 with measured flow curves

5 contact interfaces

## Results

Peak crimping force: 2.5 kN

Anvil/punch force equilibrium: within 1.8%

Internal energy: 360 mJ

Kinetic energy: negligible relative to internal energy → quasi-static
behaviour confirmed

Runtime: 453,086 cycles · 3 h 55 min on 4 cores

## Scope and Limitations

- Mass scaling with added mass ratio ≈ 231
  (target timestep: 2.7e-7 s)
- Quasi-static behaviour evaluated using KE/IE from GLSTAT
- Local contact penetration at the anvil after the ferrule is fully closed
- Anvil segments are one element across the extrusion direction
  (aspect ratio ≈ 178:1)
- Reported final state is 62 (t = 0.1214 s)
- State 63 is the termination state 0.96 ms later; during this interval
  the punch advances only 0.17 µm
- No springback step
- No experimental validation
- Runtime is dominated by strand self-contact (27% CPU)
- The current model uses AUTOMATIC_GENERAL for strand self-contact;
  AUTOMATIC_SINGLE_SURFACE could be investigated as a more efficient
  formulation

  ## Reference

This project is a self-directed reproduction of a published
wire-crimping simulation developed in Abaqus. The published model was used as a
technical reference, and the crimping process was reproduced
using LS-DYNA.

The purpose of this project was to study nonlinear forming,
contact, friction and explicit quasi-static simulation.

## Disclaimer

This is an educational/self-directed simulation and has not
been experimentally validated. Results should therefore not
be interpreted as an experimentally validated prediction of
the physical crimping process.
