FYP Veterinary Dental Final Consolidated Dataset

Targets:
- Healthy / Normal
- Plaque (feline only; canine plaque intentionally unsupported)
- Gingivitis
- Calculus / Tartar

Important:
1. This is a multi-label dataset. Disease labels may coexist.
2. mask_* columns indicate whether a target label is known/supported for that image.
   A masked label must NOT be treated as a negative during training.
3. Cat Dental Classification does not annotate calculus, so its calculus labels are masked.
4. Dog plaque is intentionally masked because reliable canine plaque ground truth was unavailable.
5. Generic dental images are included only when they passed the conservative manual visual screening.
6. Exact visual duplicates across included sources were merged before export.
7. Manually screened labels are FYP-level visual labels, not veterinarian-confirmed diagnoses.
8. Train/validation/test split has NOT been created yet.
