import { useMemo, useState } from 'react'
import { benchmarkRows, benchmarkSummary } from './data/benchmark'
import { demoMessages } from './data/messages'
import { groupMessages, visibleRoute } from './lib/groupMessages'
import { ROUTES, type FeedbackState, type Route } from './types'

const routeLabels: Record<Route, string> = {
  'NEEDS ACTION': 'Needs action',
  'NEEDS REPLY': 'Needs reply',
  'UPCOMING EVENTS': 'Upcoming events',
  INFORMATIONAL: 'Informational',
  'LOW PRIORITY': 'Low priority',
  REVIEW: 'Review',
}

function ArrowIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20">
      <path d="M4 10h11M11 5l5 5-5 5" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20">
      <path d="m4 10 4 4 8-9" />
    </svg>
  )
}

function Header() {
  return (
    <header className="site-header">
      <a className="brand" href="#top" aria-label="Signalbox home">
        <span className="brand-mark">S</span>
        <span>Signalbox</span>
      </a>
      <nav aria-label="Main navigation">
        <a href="#demo">Demo</a>
        <a href="#evidence">Evidence</a>
        <a href="#architecture">Architecture</a>
        <a href="#privacy">Privacy</a>
      </nav>
      <a
        className="github-link"
        href="https://github.com/leoxing-dev/ai-email-intelligence"
        target="_blank"
        rel="noreferrer"
      >
        View source <ArrowIcon />
      </a>
    </header>
  )
}

interface MessageCardProps {
  message: (typeof demoMessages)[number]
  feedback?: FeedbackState
  editing: boolean
  onFeedback: (feedback: FeedbackState) => void
  onEdit: (editing: boolean) => void
}

function MessageCard({ message, feedback, editing, onFeedback, onEdit }: MessageCardProps) {
  const displayedRoute = visibleRoute(message, feedback) ?? message.route
  const [draftRoute, setDraftRoute] = useState<Route>(displayedRoute)

  return (
    <article className="message-card" data-route={displayedRoute}>
      <div className="message-topline">
        <div className="sender-avatar" aria-hidden="true">
          {message.sender.slice(0, 1)}
        </div>
        <div className="message-heading">
          <div className="sender-line">
            <span>{message.sender}</span>
            <time>{message.receivedLabel}</time>
          </div>
          <h4>{message.subject}</h4>
        </div>
      </div>
      <p className="preview">{message.preview}</p>

      <div className="signal-row" aria-label="Extracted signals">
        <span className={`route-pill route-${displayedRoute.toLowerCase().replaceAll(' ', '-')}`}>
          {routeLabels[displayedRoute]}
        </span>
        <span>Action · {message.actionKind}</span>
        {message.deadline && <span>Deadline · {message.deadline}</span>}
        {message.eventDate && <span>Event · {message.eventDate}</span>}
        {message.registrationState !== 'none' && (
          <span>Registration · {message.registrationState}</span>
        )}
        <span>Reply · {String(message.needsReply)}</span>
      </div>

      <details className="why-panel">
        <summary>Why was this classified this way?</summary>
        <p>{message.explanation}</p>
        <div className="why-grid">
          <div>
            <span className="mini-label">Application evidence</span>
            <ul>
              {message.evidence.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
          <div>
            <span className="mini-label">Provenance</span>
            <ol className="pipeline-list">
              {message.pipeline.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
          </div>
        </div>
        <div className="confidence-line">
          <span>Precomputed model-only-v1</span>
          <span>{Math.round(message.confidence * 100)}% confidence</span>
        </div>
      </details>

      <div className="feedback-row" aria-label={`Feedback for ${message.subject}`}>
        <button
          className={feedback?.action === 'keep' ? 'selected' : ''}
          type="button"
          onClick={() => {
            onFeedback({ action: 'keep' })
            onEdit(false)
          }}
        >
          Keep
        </button>
        <button
          className={feedback?.action === 'ignore' ? 'selected' : ''}
          type="button"
          onClick={() => {
            onFeedback({ action: 'ignore' })
            onEdit(false)
          }}
        >
          Ignore
        </button>
        <button
          className={feedback?.action === 'correct' ? 'selected' : ''}
          type="button"
          onClick={() => onEdit(!editing)}
        >
          Correct
        </button>
      </div>

      {editing && (
        <div className="correction-panel">
          <label htmlFor={`route-${message.id}`}>Correct primary route</label>
          <select
            id={`route-${message.id}`}
            value={draftRoute}
            onChange={(event) => setDraftRoute(event.target.value as Route)}
          >
            {ROUTES.map((route) => (
              <option key={route} value={route}>
                {routeLabels[route]}
              </option>
            ))}
          </select>
          <button
            className="save-correction"
            type="button"
            onClick={() => {
              onFeedback({ action: 'correct', correctedRoute: draftRoute })
              onEdit(false)
            }}
          >
            Save correction
          </button>
        </div>
      )}
    </article>
  )
}

function InboxDemo() {
  const [analyzed, setAnalyzed] = useState(false)
  const [feedback, setFeedback] = useState<Record<string, FeedbackState>>({})
  const [editingId, setEditingId] = useState<string | null>(null)
  const groups = useMemo(() => groupMessages(demoMessages, feedback), [feedback])
  const feedbackCount = Object.keys(feedback).length
  const ignoredCount = Object.values(feedback).filter((item) => item.action === 'ignore').length

  function updateFeedback(id: string, value: FeedbackState) {
    setFeedback((current) => ({ ...current, [id]: value }))
  }

  return (
    <section className="demo-section section-shell" id="demo" aria-labelledby="demo-title">
      <div className="section-heading demo-heading">
        <div>
          <span className="eyebrow">Interactive product walkthrough</span>
          <h2 id="demo-title">From inbox noise to a reviewable plan.</h2>
          <p>
            Explore twelve purpose-built synthetic messages. The classification output is
            precomputed; every interaction stays in this browser tab.
          </p>
        </div>
        <div className="demo-notice">
          <span className="notice-dot" />
          <span>
            Synthetic data + precomputed predictions<br />
            No Gmail login or AI API request
          </span>
        </div>
      </div>

      <div className="inbox-frame">
        <div className="inbox-toolbar">
          <div>
            <span className="mini-label">Synthetic inbox</span>
            <h3>{demoMessages.length} messages</h3>
          </div>
          {!analyzed ? (
            <button className="primary-button" type="button" onClick={() => setAnalyzed(true)}>
              Analyze inbox <ArrowIcon />
            </button>
          ) : (
            <div className="analysis-state">
              <CheckIcon /> Analysis complete
            </div>
          )}
        </div>

        {!analyzed ? (
          <div className="raw-inbox" data-testid="synthetic-inbox">
            {demoMessages.map((message) => (
              <div className="raw-message" key={message.id}>
                <span className="unread-dot" aria-label="Unread" />
                <strong>{message.sender}</strong>
                <span>{message.subject}</span>
                <span className="raw-preview">— {message.preview}</span>
                <time>{message.receivedLabel}</time>
              </div>
            ))}
          </div>
        ) : (
          <div className="analysis-layout" data-testid="analyzed-inbox">
            <aside className="route-summary" aria-label="Route summary">
              <span className="mini-label">Primary routes</span>
              {ROUTES.map((route) => (
                <a href={`#group-${route.replaceAll(' ', '-').toLowerCase()}`} key={route}>
                  <span>{routeLabels[route]}</span>
                  <strong>{groups[route].length}</strong>
                </a>
              ))}
              <div className="feedback-summary">
                <span className="mini-label">Human feedback</span>
                <strong>{feedbackCount} reviewed</strong>
                <span>{ignoredCount} ignored</span>
              </div>
            </aside>

            <div className="route-groups">
              {ROUTES.map((route) => {
                const messages = groups[route]
                if (messages.length === 0) return null
                return (
                  <section
                    className="route-group"
                    id={`group-${route.replaceAll(' ', '-').toLowerCase()}`}
                    key={route}
                    aria-labelledby={`heading-${route.replaceAll(' ', '-').toLowerCase()}`}
                  >
                    <div className="group-heading">
                      <h3 id={`heading-${route.replaceAll(' ', '-').toLowerCase()}`}>
                        {routeLabels[route]}
                      </h3>
                      <span>{messages.length}</span>
                    </div>
                    {messages.map((message) => (
                      <MessageCard
                        key={message.id}
                        message={message}
                        feedback={feedback[message.id]}
                        editing={editingId === message.id}
                        onFeedback={(value) => updateFeedback(message.id, value)}
                        onEdit={(editing) => setEditingId(editing ? message.id : null)}
                      />
                    ))}
                  </section>
                )
              })}
            </div>
          </div>
        )}
      </div>

      <div className="feedback-flow" aria-label="Feedback concept">
        <div><span>01</span><strong>Prediction</strong><small>Structured, inspectable output</small></div>
        <ArrowIcon />
        <div><span>02</span><strong>User correction</strong><small>Kept in browser state only</small></div>
        <ArrowIcon />
        <div><span>03</span><strong>Evaluation feedback</strong><small>Conceptual learning signal</small></div>
      </div>
    </section>
  )
}

function EvidenceSection() {
  return (
    <section className="evidence-section section-shell" id="evidence" aria-labelledby="evidence-title">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Frozen blind evaluation</span>
          <h2 id="evidence-title">The model generalized. The hybrid did not.</h2>
        </div>
        <p>
          V3 was frozen before evaluation and contains no tuning split. Results below are the
          combined test and challenge measurements.
        </p>
      </div>

      <div className="benchmark-facts">
        <div><strong>{benchmarkSummary.cases}</strong><span>Synthetic blind cases</span></div>
        <div><strong>{benchmarkSummary.families}</strong><span>Isolated scenario families</span></div>
        <div><strong>{benchmarkSummary.hardShare}</strong><span>Hard or adversarial</span></div>
      </div>

      <div className="evidence-grid">
        <div className="metric-card">
          <div className="metric-card-heading">
            <div>
              <span className="mini-label">V3 combined</span>
              <h3>Semantic quality</h3>
            </div>
            <span className="winner-key">Best overall · Model</span>
          </div>
          <div className="table-scroll">
            <table aria-label="Frozen V3 benchmark metrics">
              <thead>
                <tr><th>Metric</th><th>Rules</th><th>Model</th><th>Hybrid</th></tr>
              </thead>
              <tbody>
                {benchmarkRows.map((row) => {
                  const maximum = Math.max(row.rules, row.model, row.hybrid)
                  return (
                    <tr key={row.label}>
                      <th>{row.label}</th>
                      <td className={row.rules === maximum ? 'best' : ''}>{row.rules.toFixed(3)}</td>
                      <td className={row.model === maximum ? 'best' : ''}>{row.model.toFixed(3)}</td>
                      <td className={row.hybrid === maximum ? 'best' : ''}>{row.hybrid.toFixed(3)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <p className="benchmark-caveat">
            These are synthetic blind benchmark results, not production Gmail accuracy.
          </p>
        </div>

        <aside className="experiment-card">
          <span className="eyebrow">A useful negative result</span>
          <h3>Development wins did not survive the blind test.</h3>
          <p>
            Hybrid-v1 looked excellent on development data, but underperformed model-only on
            blind V3. It improved deadline F1 by 0.012 while reducing route accuracy by 0.170.
          </p>
          <div className="decision-block">
            <span className="mini-label">Architecture decision</span>
            <strong>Model-first semantic extraction</strong>
            <span>+</span>
            <strong>Deterministic validation, normalization &amp; safety policy</strong>
          </div>
          <a
            href="https://github.com/leoxing-dev/ai-email-intelligence/blob/main/evaluation/FROZEN_V3_FINAL_COMPARISON.md"
            target="_blank"
            rel="noreferrer"
          >
            Read the frozen comparison <ArrowIcon />
          </a>
        </aside>
      </div>

      <div className="cost-strip" aria-label="Frozen V3 cost and latency">
        <div><span>Evaluation cost</span><strong>{benchmarkSummary.measuredCost}</strong><small>312 billable responses</small></div>
        <div><span>Average / message</span><strong>{benchmarkSummary.averageCost}</strong><small>Measured usage</small></div>
        <div><span>Per 1,000</span><strong>{benchmarkSummary.thousandCost}</strong><small>Comparable synthetic mail</small></div>
        <div><span>Latency p50</span><strong>{benchmarkSummary.p50Latency}</strong><small>Billable requests</small></div>
        <div><span>Latency p95</span><strong>{benchmarkSummary.p95Latency}</strong><small>Billable requests</small></div>
      </div>
      <p className="measurement-note">Cost and latency are frozen benchmark measurements, not pricing or latency guarantees.</p>
    </section>
  )
}

const pipelineSteps = [
  ['01', 'Input', 'Gmail or synthetic fixture'],
  ['02', 'Parse', 'MIME + sanitized HTML'],
  ['03', 'Boundary', 'Transient, minimized data'],
  ['04', 'Extract', 'Independent semantic fields'],
  ['05', 'Validate', 'Strict schema + domain rules'],
  ['06', 'Normalize', 'Canonical values and dates'],
  ['07', 'Route', 'Deterministic safety policy'],
  ['08', 'Review', 'Digest + human feedback'],
] as const

function ArchitectureSection() {
  return (
    <section className="architecture-section" id="architecture" aria-labelledby="architecture-title">
      <div className="section-shell">
        <div className="section-heading architecture-heading">
          <div>
            <span className="eyebrow">System architecture</span>
            <h2 id="architecture-title">A model can extract meaning without owning policy.</h2>
          </div>
          <p>
            Semantic fields stay independent. Validation and normalization create a stable
            contract before deterministic policy selects the primary review route.
          </p>
        </div>

        <div className="path-selector" aria-label="Demo architecture path">
          <span>Live path · Local Gmail</span>
          <strong>Public demo path · Synthetic fixtures</strong>
        </div>

        <div className="pipeline-visual">
          {pipelineSteps.map(([number, title, description], index) => (
            <div className={`pipeline-step ${index === 0 ? 'active-path' : ''}`} key={number}>
              <span>{number}</span>
              <strong>{title}</strong>
              <small>{description}</small>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function PrivacySection() {
  return (
    <section className="privacy-section section-shell" id="privacy" aria-labelledby="privacy-title">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Concrete privacy boundaries</span>
          <h2 id="privacy-title">Three modes. Three explicit contracts.</h2>
        </div>
        <p>Privacy claims are scoped to implemented controls—not comparisons with an email provider.</p>
      </div>

      <div className="privacy-grid">
        <article>
          <span className="mode-number">01</span>
          <h3>Live Gmail</h3>
          <p>Local, deterministic processing for a read-only mailbox digest.</p>
          <ul>
            <li>Exact <code>gmail.readonly</code> scope</li>
            <li>Message list/get only</li>
            <li>No writes or attachment retrieval</li>
            <li>Raw body transient, never persisted</li>
          </ul>
        </article>
        <article>
          <span className="mode-number">02</span>
          <h3>AI benchmark</h3>
          <p>Controlled model evaluation isolated from the Gmail path.</p>
          <ul>
            <li>Synthetic fixtures only</li>
            <li>OpenAI structured outputs</li>
            <li><code>store=false</code> on provider calls</li>
            <li>No live Gmail data</li>
          </ul>
        </article>
        <article className="highlight-mode">
          <span className="mode-number">03</span>
          <h3>Public demo</h3>
          <p>This static site is an inspectable, zero-credential product simulation.</p>
          <ul>
            <li>Synthetic data only</li>
            <li>Precomputed predictions</li>
            <li>No Gmail login or OpenAI key</li>
            <li>No external model calls</li>
          </ul>
        </article>
      </div>
    </section>
  )
}

function LimitationsSection() {
  return (
    <section className="limitations-section section-shell" aria-labelledby="limitations-title">
      <div className="limitations-copy">
        <span className="eyebrow">Known limitations</span>
        <h2 id="limitations-title">Evidence over theater.</h2>
        <p>
          The strongest architecture still has meaningful gaps. This project surfaces them
          instead of turning a benchmark into a production claim.
        </p>
      </div>
      <div className="limitations-list">
        <div><strong>{benchmarkSummary.deadlineFalseNegatives}</strong><span>Model deadline false negatives on combined V3</span></div>
        <div><strong>{benchmarkSummary.replyRecall}</strong><span>Model reply recall on combined V3</span></div>
        <div><strong>{benchmarkSummary.abstentions}</strong><span>Intentional model abstentions across final runs</span></div>
        <div><strong>Read-only</strong><span>No Gmail writes, automatic sending, or deletion</span></div>
        <div><strong>Synthetic</strong><span>Benchmark performance is not production accuracy</span></div>
        <div><strong>Static</strong><span>The public demo makes no live model calls</span></div>
      </div>
    </section>
  )
}

export default function App() {
  return (
    <>
      <div className="top-banner">Synthetic data · Precomputed predictions · Zero external API calls</div>
      <Header />
      <main id="top">
        <section className="hero section-shell">
          <div className="hero-copy">
            <span className="eyebrow">Privacy-first AI email intelligence</span>
            <h1>Turn an inbox into decisions you can inspect.</h1>
            <p>
              Signalbox extracts actions, deadlines, events, registration state, and reply
              signals—then validates and routes them through an explicit safety policy.
            </p>
            <div className="hero-actions">
              <a className="primary-button" href="#demo">Try the synthetic demo <ArrowIcon /></a>
              <a className="secondary-button" href="#evidence">See blind evaluation</a>
            </div>
            <div className="hero-proof">
              <div><strong>0.961</strong><span>Required-action F1</span></div>
              <div><strong>0.849</strong><span>Route accuracy</span></div>
              <div><strong>312</strong><span>Blind V3 cases</span></div>
            </div>
          </div>
          <div className="hero-visual" aria-label="Example structured email analysis">
            <div className="visual-header"><span /><span /><span /><small>structured-message.json</small></div>
            <div className="visual-email">
              <span className="mini-label">Synthetic message</span>
              <strong>Confirm workspace access by Friday</strong>
              <p>Access owners must confirm active collaborators by October 16.</p>
            </div>
            <div className="visual-output">
              <div><span>primary_route</span><strong>needs_action</strong></div>
              <div><span>action_kind</span><strong>required</strong></div>
              <div><span>deadline</span><strong>2026-10-16</strong></div>
              <div><span>needs_reply</span><strong>false</strong></div>
            </div>
            <div className="visual-status"><CheckIcon /> Schema valid · Route normalized</div>
          </div>
        </section>

        <InboxDemo />
        <EvidenceSection />
        <ArchitectureSection />
        <PrivacySection />
        <LimitationsSection />
      </main>
      <footer>
        <div className="section-shell footer-inner">
          <div><span className="brand-mark">S</span><strong>Signalbox</strong></div>
          <p>Built to make model behavior inspectable—and uncertainty visible.</p>
          <a href="https://github.com/leoxing-dev/ai-email-intelligence" target="_blank" rel="noreferrer">GitHub <ArrowIcon /></a>
        </div>
      </footer>
    </>
  )
}
