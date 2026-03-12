import { Component } from 'preact';
import type { ComponentChildren } from 'preact';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Props {
  children: ComponentChildren;
}

interface State {
  hasError: boolean;
  error: Error | null;
  componentStack: string;
}

// ─── Styles ───────────────────────────────────────────────────────────────────

// Inline styles keep this component self-contained so it renders correctly even
// when MUI / ThemeProvider are unavailable (e.g. if App itself throws on mount).

const S = {
  root: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#0d1117',
    color: '#e6edf3',
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    padding: '2rem',
    boxSizing: 'border-box' as const,
  },
  card: {
    maxWidth: 600,
    width: '100%',
  },
  heading: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.75rem',
    marginBottom: '1rem',
  },
  title: {
    margin: 0,
    fontSize: '1.25rem',
    fontWeight: 600 as const,
    color: '#f85149',
  },
  subtitle: {
    margin: '0 0 1.25rem',
    color: '#8b949e',
    fontSize: '0.875rem',
    lineHeight: 1.6,
  },
  pre: {
    backgroundColor: '#161b22',
    border: '1px solid #30363d',
    borderRadius: 6,
    padding: '1rem',
    fontSize: '0.75rem',
    overflowX: 'auto' as const,
    whiteSpace: 'pre-wrap' as const,
    wordBreak: 'break-word' as const,
    margin: '0 0 1rem',
  },
  errorPre: {
    color: '#f85149',
  },
  stackPre: {
    color: '#8b949e',
    fontSize: '0.7rem',
  },
  summary: {
    cursor: 'pointer',
    color: '#8b949e',
    fontSize: '0.75rem',
    marginBottom: '0.5rem',
    userSelect: 'none' as const,
  },
  button: {
    marginTop: '1.5rem',
    padding: '0.5rem 1.25rem',
    backgroundColor: '#1f6feb',
    color: '#ffffff',
    border: 'none',
    borderRadius: 6,
    fontSize: '0.875rem',
    fontWeight: 500 as const,
    cursor: 'pointer',
    fontFamily: 'inherit',
  },
} as const;

// ─── Component ────────────────────────────────────────────────────────────────

/**
 * ErrorBoundary
 *
 * Catches synchronous render errors thrown anywhere in the component tree
 * below it and displays a friendly error card with the error message and
 * (optionally) the component stack trace.
 *
 * Uses only inline styles so it remains usable even when MUI fails to mount.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null, componentStack: '' };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: { componentStack?: string }) {
    console.error('[ErrorBoundary] Render error caught:', error);
    if (info.componentStack) {
      this.setState({ componentStack: info.componentStack });
    }
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    const { error, componentStack } = this.state;

    return (
      <div style={S.root}>
        <div style={S.card}>

          {/* ── Heading ──────────────────────────────────────────────────── */}
          <div style={S.heading}>
            {/* Warning triangle icon */}
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"
                stroke="#f85149"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
              <line x1="12" y1="9" x2="12" y2="13" stroke="#f85149" stroke-width="2" stroke-linecap="round" />
              <line x1="12" y1="17" x2="12.01" y2="17" stroke="#f85149" stroke-width="2" stroke-linecap="round" />
            </svg>
            <h1 style={S.title}>Dashboard Error</h1>
          </div>

          {/* ── Message ──────────────────────────────────────────────────── */}
          <p style={S.subtitle}>
            An unexpected error occurred while rendering the dashboard.
            The ESP32 device itself is unaffected and continues to run normally.
          </p>

          {/* ── Error message ────────────────────────────────────────────── */}
          {error && (
            <pre style={{ ...S.pre, ...S.errorPre }}>
              {error.name}: {error.message}
            </pre>
          )}

          {/* ── Component stack (collapsible) ────────────────────────────── */}
          {componentStack && (
            <details>
              <summary style={S.summary}>Component stack</summary>
              <pre style={{ ...S.pre, ...S.stackPre }}>{componentStack}</pre>
            </details>
          )}

          {/* ── Reload button ────────────────────────────────────────────── */}
          <div>
            <button
              type="button"
              style={S.button}
              onClick={() => window.location.reload()}
            >
              Reload page
            </button>
          </div>

        </div>
      </div>
    );
  }
}
