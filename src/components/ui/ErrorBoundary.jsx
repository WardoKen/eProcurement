import { Component } from 'react'
import { AlertTriangle } from 'lucide-react'

// Catches render errors in one screen so the rest of the app (navigation,
// session) keeps working. Offers recovery: retry the screen, reload, or go
// home. `resetKey` clears the error when the user navigates elsewhere.
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null, resetKey: props.resetKey }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  static getDerivedStateFromProps(props, state) {
    if (props.resetKey !== state.resetKey) return { error: null, resetKey: props.resetKey }
    return null
  }

  componentDidCatch(error, info) {
    console.error('Screen failed to render:', error, info?.componentStack)
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children

    return (
      <section className="error-boundary" role="alert">
        <AlertTriangle size={32} aria-hidden="true" />
        <h2>{this.props.title || 'This screen could not be displayed'}</h2>
        <p>
          Something went wrong while showing this part of eProcure. Your saved records are not affected.
          Try again, or reload the page if the problem continues.
        </p>
        <div className="error-boundary-actions">
          <button type="button" className="btn btn-primary" onClick={() => this.setState({ error: null })}>Try again</button>
          <button type="button" className="btn btn-secondary" onClick={() => window.location.reload()}>Reload page</button>
          {this.props.homeHref && <a className="btn btn-outline" href={this.props.homeHref}>Go to home</a>}
        </div>
        <details>
          <summary>Technical details</summary>
          <pre>{String(error?.message || error)}</pre>
        </details>
      </section>
    )
  }
}
