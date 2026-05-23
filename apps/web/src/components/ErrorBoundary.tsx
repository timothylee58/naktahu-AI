"use client";

import * as Sentry from "@sentry/nextjs";
import React from "react";

interface Props {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

interface State {
  hasError: boolean;
  eventId: string | null;
}

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, eventId: null };
  }

  static getDerivedStateFromError(): Partial<State> {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    const eventId = Sentry.captureException(error, {
      contexts: { react: { componentStack: info.componentStack ?? "" } },
    });
    this.setState({ eventId });
  }

  handleReport = (): void => {
    if (this.state.eventId) {
      Sentry.showReportDialog({ eventId: this.state.eventId });
    }
  };

  handleRetry = (): void => {
    this.setState({ hasError: false, eventId: null });
  };

  render(): React.ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-8 text-center">
          <h1 className="text-2xl font-semibold">Sesuatu telah berlaku</h1>
          <p className="text-muted-foreground max-w-sm">
            Something went wrong. Our team has been notified. You can try again
            or report what happened.
          </p>
          <div className="flex gap-3">
            <button
              onClick={this.handleRetry}
              className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground"
            >
              Try again
            </button>
            {this.state.eventId && (
              <button
                onClick={this.handleReport}
                className="rounded-md border px-4 py-2 text-sm"
              >
                Report
              </button>
            )}
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
