/**
 * Ink display presets (IQ-1 PR4).
 * Document/ops still store raw [x,y,t,pressure]; these curves only affect canvas paint.
 */
window.apeSketchBrush = {
  USE_INK_PREDICT: true,
  /** px/ms at which the velocity taper saturates */
  SPEED_REF: 3,
  /** Subdivide segments longer than this (page px) */
  SPLIT_PX: 3,
  STEP_PX: 1.5,
  MAX_SPLITS: 8,
  /** Predicted tip horizon (ms) and max extra length (px) */
  PREDICT_MS: 16,
  PREDICT_MAX_PX: 8,
  pen: {
    round: { pressure: [0.35, 1.3], velocity: -0.15, inertia: 1 },
    square: { pressure: [0.4, 1.2], velocity: -0.1, inertia: 1 },
    chisel: { pressure: [0.5, 1.0], velocity: -0.05, inertia: 1 },
  },
  fountain: {
    round: { pressure: [0.45, 1.8], velocity: -0.2, inertia: 0.35 },
    square: { pressure: [0.45, 1.8], velocity: -0.2, inertia: 0.35 },
    chisel: { pressure: [0.45, 1.8], velocity: -0.15, inertia: 0.35 },
  },
  chalk: {
    round: { pressure: [0.55, 1.05], velocity: -0.08, inertia: 1 },
    square: { pressure: [0.55, 1.05], velocity: -0.08, inertia: 1 },
    chisel: { pressure: [0.55, 1.05], velocity: -0.06, inertia: 1 },
  },
};
