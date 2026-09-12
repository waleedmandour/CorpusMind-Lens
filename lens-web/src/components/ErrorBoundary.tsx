import React from "react";

interface State {
  error: Error | null;
}

/**
 * Root error boundary. A render crash used to unmount the whole tree and
 * leave a blank white window; now it shows the error with a recovery path.
 * Styles are inline on purpose: the boundary must render even if the
 * stylesheet itself failed to load.
 */
export class ErrorBoundary extends React.Component<{ children: React.ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // Best-effort console trail for the desktop log collector.
    console.error("lens-ui-crash", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    const msg = this.state.error.message || String(this.state.error);
    return (
      <div
        role="alert"
        style={{
          minHeight: "100vh",
          display: "grid",
          placeItems: "center",
          background: "#f8fafc",
          color: "#0f172a",
          fontFamily: "system-ui, sans-serif",
          padding: 24,
        }}
      >
        <div
          style={{
            maxWidth: 640,
            background: "#fff",
            border: "1px solid #e2e8f0",
            borderInlineStart: "4px solid #dc2626",
            borderRadius: 12,
            padding: 24,
            boxShadow: "0 8px 24px rgba(15,23,42,.08)",
          }}
        >
          <h1 style={{ fontSize: 18, margin: "0 0 8px" }}>
            Something went wrong while rendering the interface
          </h1>
          <p style={{ fontSize: 13, margin: "0 0 12px", lineHeight: 1.6 }}>
            The error details below help diagnose the problem. Reloading usually
            recovers. If it persists, remove the app data directory
            (~/.lens-engine-data) and reinstall.
          </p>
          <pre
            style={{
              fontSize: 12,
              background: "#f1f5f9",
              border: "1px solid #e2e8f0",
              borderRadius: 8,
              padding: 12,
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              maxHeight: 200,
              overflow: "auto",
              margin: "0 0 16px",
            }}
          >
            {msg}
          </pre>
          <button
            onClick={() => window.location.reload()}
            style={{
              background: "#2563eb",
              color: "#fff",
              border: "none",
              borderRadius: 8,
              padding: "8px 16px",
              fontSize: 13,
              cursor: "pointer",
            }}
          >
            Reload CorpusMind Lens
          </button>
        </div>
      </div>
    );
  }
}
