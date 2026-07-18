"""Orchestration observability & safety layer.

This package provides the monitoring, safety, and session management
infrastructure for the multi-agent orchestration system:

- telemetry: structured span tracking with ring buffer
- safety: unified output safety scanner (regex-based red-flag detection)
- metrics: per-agent performance counters and latency histograms
- session_manager: TTL-based cleanup of abandoned agent sessions
"""
