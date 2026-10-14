import { describe, expect, it } from 'vitest'
import { demoMessages } from './messages'

describe('synthetic demo fixtures', () => {
  it('loads exactly twelve entirely synthetic messages', () => {
    expect(demoMessages).toHaveLength(12)
    expect(new Set(demoMessages.map((message) => message.id)).size).toBe(12)
    expect(demoMessages.every((message) => message.senderAddress.endsWith('.example'))).toBe(true)
  })

  it('covers the intended routing surface', () => {
    const routes = new Set(demoMessages.map((message) => message.route))
    expect(routes).toEqual(
      new Set([
        'NEEDS ACTION',
        'NEEDS REPLY',
        'UPCOMING EVENTS',
        'INFORMATIONAL',
        'LOW PRIORITY',
        'REVIEW',
      ]),
    )
  })
})
