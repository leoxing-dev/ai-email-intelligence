export const ROUTES = [
  'NEEDS ACTION',
  'NEEDS REPLY',
  'UPCOMING EVENTS',
  'INFORMATIONAL',
  'LOW PRIORITY',
  'REVIEW',
] as const

export type Route = (typeof ROUTES)[number]
export type ActionKind = 'required' | 'optional' | 'none' | 'uncertain'
export type RegistrationState = 'none' | 'optional' | 'required' | 'completed'
export type FeedbackAction = 'keep' | 'ignore' | 'correct'

export interface DemoMessage {
  id: string
  sender: string
  senderAddress: string
  subject: string
  preview: string
  receivedLabel: string
  route: Route
  actionKind: ActionKind
  deadline?: string
  eventDate?: string
  registrationState: RegistrationState
  needsReply: boolean | 'uncertain'
  confidence: number
  explanation: string
  evidence: string[]
  pipeline: string[]
}

export interface FeedbackState {
  action: FeedbackAction
  correctedRoute?: Route
}

export interface BenchmarkRow {
  label: string
  rules: number
  model: number
  hybrid: number
}
