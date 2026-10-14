import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('public recruiter demo', () => {
  it('renders frozen benchmark metrics and the synthetic-results caveat', () => {
    render(<App />)
    const table = screen.getByRole('table', { name: /frozen v3 benchmark metrics/i })

    expect(within(table).getByText('0.961')).toBeInTheDocument()
    expect(within(table).getByText('0.849')).toBeInTheDocument()
    expect(screen.getByText(/not production Gmail accuracy/i)).toBeInTheDocument()
  })

  it('moves a message when a user corrects its route', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: /analyze inbox/i }))
    const accessCard = screen
      .getByRole('heading', { name: 'Confirm workspace access by Friday', level: 4 })
      .closest('article')
    expect(accessCard).not.toBeNull()

    await user.click(within(accessCard!).getByRole('button', { name: 'Correct' }))
    await user.selectOptions(
      within(accessCard!).getByRole('combobox', { name: /correct primary route/i }),
      'REVIEW',
    )
    await user.click(within(accessCard!).getByRole('button', { name: /save correction/i }))

    const correctedCard = screen
      .getByRole('heading', { name: 'Confirm workspace access by Friday', level: 4 })
      .closest('article')
    expect(correctedCard).toHaveAttribute('data-route', 'REVIEW')
    expect(within(correctedCard!).getByText('Review')).toBeInTheDocument()
  })

  it('does not make external requests while loading or analyzing', async () => {
    const requestSpy = vi.fn()
    vi.stubGlobal('fetch', requestSpy)
    const user = userEvent.setup()

    render(<App />)
    await user.click(screen.getByRole('button', { name: /analyze inbox/i }))
    expect(screen.getByTestId('analyzed-inbox')).toBeInTheDocument()
    expect(requestSpy).not.toHaveBeenCalled()
  })
})
