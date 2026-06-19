# Steroid Sensor Design — plan (stub fixture for smoke test)
Goal: ML model predicting steroid-ligand binding to engineered AcrR mutants.
Approach: template-pose docking -> 84-dim contact fingerprint -> XGBoost.
Train on nuclear-receptor binding data, transfer to AcrR mutants.
