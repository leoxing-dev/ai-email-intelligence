import { ROUTES, type DemoMessage, type FeedbackState, type Route } from '../types'

export type MessageGroups = Record<Route, DemoMessage[]>

export function visibleRoute(
  message: DemoMessage,
  feedback?: FeedbackState,
): Route | null {
  if (feedback?.action === 'ignore') return null
  return feedback?.correctedRoute ?? message.route
}

export function groupMessages(
  messages: DemoMessage[],
  feedback: Record<string, FeedbackState> = {},
): MessageGroups {
  const groups = ROUTES.reduce<MessageGroups>((result, route) => {
    result[route] = []
    return result
  }, {
    'NEEDS ACTION': [],
    'NEEDS REPLY': [],
    'UPCOMING EVENTS': [],
    INFORMATIONAL: [],
    'LOW PRIORITY': [],
    REVIEW: [],
  })

  for (const message of messages) {
    const route = visibleRoute(message, feedback[message.id])
    if (route) groups[route].push(message)
  }

  return groups
}
