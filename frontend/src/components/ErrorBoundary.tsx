import { Component, type ReactNode } from "react";

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<
  { children: ReactNode },
  State
> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="p-8 text-center">
          <h2 className="text-lg font-semibold text-panel-danger mb-2">
            Something went wrong
          </h2>
          <p className="text-slate-400 text-sm">{this.state.error.message}</p>
          <button
            className="mt-4 text-panel-accent underline"
            onClick={() => this.setState({ error: null })}
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
