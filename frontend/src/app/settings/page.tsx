'use client';

import { useState, useEffect } from 'react';
import {
  Server, Database, Cpu,
  ShieldCheck, AlertCircle, Info, RefreshCw
} from 'lucide-react';
import AppShell from '@/components/AppShell';
import { api, type SafeSettings } from '@/lib/api';

interface HealthData {
  status: string;
  database?: string;
  schema_revision?: string;
  version?: string;
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<SafeSettings | null>(null);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = () => {
    setLoading(true);
    setError(null);
    Promise.all([
      api.getSettings().catch(() => null),
      api.health().catch(() => null),
    ])
      .then(([s, h]) => {
        setSettings(s);
        setHealth(h);
        if (!s && !h) {
          setError('Unable to load settings from backend. Please ensure the server is running on port 8000.');
        }
        setLoading(false);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : 'Failed to fetch settings');
        setLoading(false);
      });
  };

  useEffect(() => {
    let ignore = false;
    Promise.all([
      api.getSettings().catch(() => null),
      api.health().catch(() => null),
    ])
      .then(([s, h]) => {
        if (!ignore) {
          setSettings(s);
          setHealth(h);
          if (!s && !h) {
            setError('Unable to load settings from backend. Please ensure the server is running on port 8000.');
          }
          setLoading(false);
        }
      })
      .catch((e) => {
        if (!ignore) {
          setError(e instanceof Error ? e.message : 'Failed to fetch settings');
          setLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, []);

  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

  return (
    <AppShell>
      {/* ── Page Header ── */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Settings & System Info</h1>
          <p className="page-subtitle">
            Read-only runtime environment, database schema status, and system configuration
          </p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={loadData} disabled={loading}>
          <RefreshCw size={13} className={loading ? 'spinner' : ''} /> Refresh
        </button>
      </div>

      {/* ── Error Banner ── */}
      {error && (
        <div className="alert alert-warning mb-4">
          <AlertCircle size={16} />
          <div>{error}</div>
        </div>
      )}

      {/* ── Environment & API Info Card ── */}
      <div className="card mb-6">
        <h3 style={{ fontSize: '1.05rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Server size={18} color="var(--accent-primary)" /> Backend & Environment
        </h3>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem' }}>
          <div style={{ background: 'var(--bg-elevated)', padding: '0.875rem 1rem', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Application Environment
            </div>
            <div style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.25rem' }}>
              {settings?.app_env ? (
                <span className="badge badge-purple">{settings.app_env}</span>
              ) : (
                <span className="text-muted">Loading...</span>
              )}
            </div>
          </div>

          <div style={{ background: 'var(--bg-elevated)', padding: '0.875rem 1rem', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              API Base URL
            </div>
            <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--accent-secondary)', marginTop: '0.25rem', fontFamily: 'var(--font-mono)' }}>
              {apiBaseUrl}
            </div>
          </div>

          <div style={{ background: 'var(--bg-elevated)', padding: '0.875rem 1rem', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Backend Health Status
            </div>
            <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.25rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              {health ? (
                <span className={`badge ${health.status === 'ok' ? 'badge-green' : 'badge-orange'}`}>
                  {health.status}
                </span>
              ) : (
                <span className="badge badge-red">Offline</span>
              )}
            </div>
          </div>

          <div style={{ background: 'var(--bg-elevated)', padding: '0.875rem 1rem', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Backend Version
            </div>
            <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.25rem' }}>
              {health?.version ?? 'v0.1.0'}
            </div>
          </div>
        </div>
      </div>

      {/* ── Database Status Card ── */}
      <div className="card mb-6">
        <h3 style={{ fontSize: '1.05rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Database size={18} color="var(--accent-secondary)" /> Database & Schema Status
        </h3>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem' }}>
          <div style={{ background: 'var(--bg-elevated)', padding: '0.875rem 1rem', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Database Connectivity
            </div>
            <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.25rem' }}>
              <span className={`badge ${health?.database === 'up' ? 'badge-green' : 'badge-red'}`}>
                {health?.database ?? 'unknown'}
              </span>
            </div>
          </div>

          <div style={{ background: 'var(--bg-elevated)', padding: '0.875rem 1rem', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Alembic Schema Revision
            </div>
            <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.25rem', fontFamily: 'var(--font-mono)' }}>
              {health?.schema_revision ?? 'None (unversioned)'}
            </div>
          </div>
        </div>
      </div>

      {/* ── AI & Crawler Configuration Card ── */}
      <div className="card mb-6">
        <h3 style={{ fontSize: '1.05rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Cpu size={18} color="var(--accent-green)" /> AI Model & Engine Config
        </h3>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem' }}>
          <div style={{ background: 'var(--bg-elevated)', padding: '0.875rem 1rem', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Active LLM Provider
            </div>
            <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.25rem' }}>
              {settings?.llm_provider ?? 'anthropic'}
            </div>
          </div>

          <div style={{ background: 'var(--bg-elevated)', padding: '0.875rem 1rem', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Configured Model Name
            </div>
            <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--accent-secondary)', marginTop: '0.25rem', fontFamily: 'var(--font-mono)' }}>
              {settings?.llm_model ?? 'claude-sonnet-5-5'}
            </div>
          </div>

          <div style={{ background: 'var(--bg-elevated)', padding: '0.875rem 1rem', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Crawl Rate Limit
            </div>
            <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.25rem' }}>
              {settings?.crawl_rate_limit_rps ?? 1.0} req/sec
            </div>
          </div>

          <div style={{ background: 'var(--bg-elevated)', padding: '0.875rem 1rem', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Max Upload Size
            </div>
            <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.25rem' }}>
              {settings?.max_upload_size_mb ?? 50} MB
            </div>
          </div>
        </div>
      </div>

      {/* ── Security & Architecture Notice ── */}
      <div className="card mb-6" style={{ background: 'rgba(124,58,237,0.03)', borderColor: 'rgba(124,58,237,0.2)' }}>
        <div className="flex items-start gap-3">
          <ShieldCheck size={20} color="var(--accent-primary)" style={{ flexShrink: 0, marginTop: '2px' }} />
          <div>
            <h4 style={{ fontSize: '0.95rem', color: 'var(--text-primary)', marginBottom: '0.35rem' }}>
              Security & Credential Isolation
            </h4>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              All API keys, database credentials, secret keys, and passwords are strictly isolated within backend
              environment variables and are never transmitted over the network or exposed to the client interface.
            </p>
          </div>
        </div>
      </div>

      {/* ── Feature Availability Reference ── */}
      <div className="card">
        <h3 style={{ fontSize: '1.05rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Info size={16} color="var(--text-tertiary)" /> Feature Availability & Roadmap
        </h3>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {[
            { label: 'Custom Crawler Rate Tuning', status: 'not yet configurable here (managed via backend .env)' },
            { label: 'LLM Temperature & Prompt Config', status: 'not yet configurable here (managed via backend .env)' },
            { label: 'Automatic Apply Notifications', status: 'not yet configurable here (scheduled in Phase 8)' },
            { label: 'Multi-User Authentication', status: 'not yet configurable here (scheduled in Phase 9)' },
          ].map(({ label, status }) => (
            <div
              key={label}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.625rem 0.875rem',
                background: 'var(--bg-elevated)',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.85rem',
              }}
            >
              <span style={{ color: 'var(--text-primary)' }}>{label}</span>
              <span className="badge badge-gray" style={{ fontSize: '0.68rem', textTransform: 'none' }}>
                {status}
              </span>
            </div>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
