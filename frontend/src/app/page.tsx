'use client';

import { useState, useEffect } from 'react';
import {
  Activity, Briefcase, Building2, CheckCircle2, Clock, FileText,
  TrendingUp, AlertCircle, Zap, RefreshCw, ExternalLink
} from 'lucide-react';
import AppShell from '@/components/AppShell';
import { api, type DashboardStats } from '@/lib/api';
import Link from 'next/link';

// ── Stat Card ─────────────────────────────────────────────────────────────────

interface StatCardProps {
  label: string;
  value: number | string;
  icon: React.ReactNode;
  color: string;
  sub?: string;
  href?: string;
}

function StatCard({ label, value, icon, color, sub, href }: StatCardProps) {
  const isStringValue = typeof value === 'string';
  const content = (
    <div className="stat-card">
      <div className="stat-icon" style={{ background: `${color}20`, border: `1px solid ${color}40` }}>
        {icon}
      </div>
      <div
        className="stat-value"
        style={isStringValue ? { fontSize: '1.05rem', fontWeight: 600, color: 'var(--text-secondary)', letterSpacing: 'normal' } : undefined}
      >
        {typeof value === 'number' ? value.toLocaleString() : value}
      </div>
      <div className="stat-label">{label}</div>
      {sub && <div className="text-xs text-faint" style={{ marginTop: '0.25rem' }}>{sub}</div>}
    </div>
  );
  return href ? <Link href={href} style={{ textDecoration: 'none' }}>{content}</Link> : content;
}

// ── Activity Feed (placeholder) ───────────────────────────────────────────────

const ACTIVITY_PLACEHOLDER = [
  { time: 'Just now', text: 'Ready to discover jobs', type: 'info' },
  { time: '', text: 'Upload your resume to enable personalized matching', type: 'warn' },
  { time: '', text: 'Run Discovery to find open roles at Bangalore startups', type: 'info' },
];

// ── Main Dashboard ────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [backendUp, setBackendUp] = useState<boolean | null>(null);
  const [discovering, setDiscovering] = useState(false);
  const [lastRunStats, setLastRunStats] = useState<Record<string, number> | null>(null);

  const loadStats = async () => {
    try {
      const s = await api.getDashboardStats();
      setStats(s);
      setBackendUp(true);
    } catch {
      setBackendUp(false);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let ignore = false;
    api
      .getDashboardStats()
      .then((s) => {
        if (!ignore) {
          setStats(s);
          setBackendUp(true);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!ignore) {
          setBackendUp(false);
          setLoading(false);
        }
      });
    return () => {
      ignore = true;
    };
  }, []);

  const runDiscovery = async () => {
    setDiscovering(true);
    try {
      const result = await api.triggerDiscovery({ max_companies: 20, fetch_jd: false });
      setLastRunStats(result.stats);
      await loadStats();
    } catch (e) {
      console.error(e);
    } finally {
      setDiscovering(false);
    }
  };

  const STATS = stats ? [
    { label: 'Companies', value: stats.total_companies, icon: <Building2 size={18} color="#7c3aed" />, color: '#7c3aed', href: '/companies', sub: 'Real database count' },
    { label: 'Jobs Discovered', value: stats.total_jobs, icon: <Briefcase size={18} color="#06b6d4" />, color: '#06b6d4', href: '/jobs', sub: 'Real database count' },
    { label: 'Open Roles', value: stats.open_jobs, icon: <TrendingUp size={18} color="#10b981" />, color: '#10b981', href: '/jobs', sub: 'Active listings' },
    { label: 'Eligible Jobs', value: 'Not available yet', icon: <CheckCircle2 size={18} color="#10b981" />, color: '#10b981', sub: 'Scheduled in Phase 6' },
    { label: 'High Matches', value: 'Not available yet', icon: <Zap size={18} color="#f59e0b" />, color: '#f59e0b', sub: 'Scheduled in Phase 6' },
    { label: 'Awaiting Review', value: 'Not available yet', icon: <Clock size={18} color="#f59e0b" />, color: '#f59e0b', href: '/applications', sub: 'Scheduled in Phase 8' },
    { label: 'Applied', value: 'Not available yet', icon: <FileText size={18} color="#ec4899" />, color: '#ec4899', href: '/applications', sub: 'Scheduled in Phase 8' },
    { label: 'Total Applications', value: 'Not available yet', icon: <CheckCircle2 size={18} color="#06b6d4" />, color: '#06b6d4', href: '/applications', sub: 'Scheduled in Phase 8' },
  ] : [];

  return (
    <AppShell>
      {/* ── Page header ── */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">
            AI-powered job discovery for Bangalore startups
            {stats?.last_discovery_at && (
              <span className="text-faint"> · Last discovery: {new Date(stats.last_discovery_at).toLocaleDateString()}</span>
            )}
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <button className="btn btn-secondary btn-sm" onClick={loadStats}>
            <RefreshCw size={14} /> Refresh
          </button>
          <button
            className="btn btn-primary"
            onClick={runDiscovery}
            disabled={discovering || !backendUp}
          >
            {discovering ? <><div className="spinner" style={{ width: 14, height: 14 }} /> Discovering...</>
              : <><Zap size={14} /> Run Discovery</>}
          </button>
        </div>
      </div>

      {/* ── Backend status banner ── */}
      {backendUp === false && (
        <div className="alert alert-warning mb-4">
          <AlertCircle size={16} />
          <div>
            <strong>Backend not reachable</strong> — make sure the FastAPI server is running on port 8000.
            <code style={{ marginLeft: '0.5rem', fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
              cd backend && python -m uvicorn app.main:app --reload
            </code>
          </div>
        </div>
      )}

      {/* ── Profile CTA ── */}
      {!stats?.has_confirmed_profile && backendUp && (
        <div style={{
          background: 'linear-gradient(135deg, rgba(124,58,237,0.12) 0%, rgba(6,182,212,0.08) 100%)',
          border: '1px solid rgba(124,58,237,0.25)',
          borderRadius: 'var(--radius-xl)',
          padding: '1.5rem 2rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1rem',
          marginBottom: '1.5rem',
        }}>
          <div>
            <h3 style={{ marginBottom: '0.375rem' }}>👋 Welcome! Upload your resume to get started</h3>
            <p className="text-sm text-muted">
              Job discovery works without a profile. Upload your resume to enable personalized
              eligibility evaluation, match scoring, and resume tailoring.
            </p>
          </div>
          <Link href="/onboarding" className="btn btn-primary" style={{ flexShrink: 0 }}>
            Upload Resume →
          </Link>
        </div>
      )}

      {/* ── Stats grid ── */}
      {loading ? (
        <div className="stats-grid">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="stat-card">
              <div className="skeleton" style={{ width: 40, height: 40, borderRadius: 'var(--radius-md)', marginBottom: '0.875rem' }} />
              <div className="skeleton" style={{ width: '60%', height: 32, marginBottom: '0.25rem' }} />
              <div className="skeleton" style={{ width: '80%', height: 14 }} />
            </div>
          ))}
        </div>
      ) : (
        <div className="stats-grid">
          {STATS.map((s) => <StatCard key={s.label} {...s} />)}
        </div>
      )}

      {/* ── Last run stats ── */}
      {lastRunStats && (
        <div className="card mb-6">
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle2 size={16} color="var(--accent-green)" />
            <h3 style={{ fontSize: '1rem', color: 'var(--accent-green)' }}>Discovery Complete</h3>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: '0.75rem' }}>
            {Object.entries(lastRunStats).map(([k, v]) => (
              <div key={k} style={{ background: 'var(--bg-elevated)', padding: '0.625rem 0.875rem', borderRadius: 'var(--radius-md)' }}>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)' }}>{v}</div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>{k.replace(/_/g, ' ')}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Two-column: Activity + Quick links ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '1.25rem' }}>

        {/* Activity */}
        <div className="card">
          <h3 style={{ fontSize: '1rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Activity size={16} color="var(--accent-secondary)" /> Recent Activity
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
            {ACTIVITY_PLACEHOLDER.map((a, i) => (
              <div key={i} style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.75rem',
                padding: '0.625rem',
                background: 'var(--bg-elevated)',
                borderRadius: 'var(--radius-md)',
              }}>
                <div className={`status-dot ${a.type === 'warn' ? 'warning' : 'active'}`} style={{ marginTop: '0.35rem' }} />
                <div>
                  <div style={{ fontSize: '0.875rem', color: 'var(--text-primary)' }}>{a.text}</div>
                  {a.time && <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', marginTop: '2px' }}>{a.time}</div>}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Quick Links */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
          <div className="card">
            <h3 style={{ fontSize: '0.95rem', marginBottom: '0.875rem' }}>Quick Actions</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {[
                { href: '/jobs',       icon: <Briefcase size={14} />,  label: 'Browse all jobs' },
                { href: '/onboarding', icon: <FileText size={14} />,   label: 'Upload resume' },
                { href: '/discovery',  icon: <Zap size={14} />,        label: 'Configure discovery' },
                { href: '/applications', icon: <CheckCircle2 size={14} />, label: 'Application tracker' },
              ].map(({ href, icon, label }) => (
                <Link
                  key={href}
                  href={href}
                  className="flex items-center gap-2"
                  style={{
                    padding: '0.5rem 0.75rem',
                    borderRadius: 'var(--radius-md)',
                    color: 'var(--text-secondary)',
                    fontSize: '0.875rem',
                    background: 'var(--bg-elevated)',
                    textDecoration: 'none',
                    transition: 'var(--transition-fast)',
                  }}
                >
                  {icon} {label}
                  <ExternalLink size={11} style={{ marginLeft: 'auto', opacity: 0.4 }} />
                </Link>
              ))}
            </div>
          </div>

          <div className="card">
            <h3 style={{ fontSize: '0.95rem', marginBottom: '0.5rem' }}>Source</h3>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', marginBottom: '0.75rem' }}>
              Jobs are discovered from Bangalore Startup Map, refreshed on demand.
            </p>
            <a
              href="https://www.bangalorestartupmap.com/?hiring=1"
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-ghost btn-sm"
              style={{ width: '100%', justifyContent: 'center' }}
            >
              <ExternalLink size={12} /> View BSM
            </a>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
