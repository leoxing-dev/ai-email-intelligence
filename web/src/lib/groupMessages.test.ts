import { describe, expect, it } from 'vitest'
import { demoMessages } from '../data/messages'
import { groupMessages } from './groupMessages'

describe('route grouping', () => {
  it('groups every visible fixture by its final route', () => {
    const groups = groupMessages(demoMessages)
    const groupedCount = Object.values(groups).flat().length

    expect(groupedCount).toBe(12)
    expect(groups['NEEDS ACTION'].map((message) => message.id)).toContain('demo-access-review')
    expect(groups['NEEDS REPLY']).toHaveLength(1)
    expect(groups.REVIEW).toHaveLength(1)
  })

  it('applies browser-only ignore and correction feedback', () => {
    const groups = groupMessages(demoMessages, {
      'demo-access-review': { action: 'correct', correctedRoute: 'REVIEW' },
      'demo-promotion-urgent': { action: 'ignore' },
    })

    expect(groups.REVIEW.map((message) => message.id)).toContain('demo-access-review')
    expect(Object.values(groups).flat().map((message) => message.id)).not.toContain(
      'demo-promotion-urgent',
    )
  })
})
