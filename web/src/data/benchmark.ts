import type { BenchmarkRow } from '../types'

// Frozen V3 combined values from evaluation/FROZEN_V3_FINAL_RESULTS.json.
export const benchmarkRows: BenchmarkRow[] = [
  { label: 'Required action F1', rules: 0.731, model: 0.961, hybrid: 0.768 },
  { label: 'Event F1', rules: 0.927, model: 0.964, hybrid: 0.937 },
  { label: 'Upcoming event F1', rules: 0.952, model: 0.992, hybrid: 0.969 },
  { label: 'Deadline F1', rules: 0.828, model: 0.816, hybrid: 0.828 },
  { label: 'Route accuracy', rules: 0.532, model: 0.849, hybrid: 0.679 },
]

export const benchmarkSummary = {
  cases: 312,
  families: 52,
  hardShare: '69.2%',
  measuredCost: '$1.59',
  averageCost: '$0.0051',
  thousandCost: '$5.10',
  p50Latency: '3.28 s',
  p95Latency: '4.56 s',
  deadlineFalseNegatives: 28,
  replyRecall: '0.111',
  abstentions: 31,
} as const
