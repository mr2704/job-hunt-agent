'use client';

import { useState, useEffect } from 'react';
import {
  FileText, Clock, CheckCircle2, AlertCircle, ArrowRight,
  Briefcase
} from 'lucide-react';
import AppShell from '@/components/AppShell';
import { api, type DashboardStats } from '@/lib/api';
import Link from 'next/link';

export default function ApplicationsPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    api.getDashboardStats()
      .then((s) => {
        if (!ignore) {
          setStats(s);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!ignore) {
          setError(err instanceof Error ? err.message : 'Unable to load application metrics');
          setLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, []);

  return (
    <AppShell>
      {/* ── Page Header ── */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Applications Tracker</h1>
          <p className="page-subtitle">
            Track submission status, review tailored resumes, and manage interview schedules
          </p>
        </div>
        <Link href="/jobs" className="btn btn-primary btn-sm">
          Browse Jobs to Apply <ArrowRight size={13} />
        </Link>
      </div>

      {/* ── Error Banner ── */}
      {error && (
        <div className="alert alert-warning mb-4">
          <AlertCircle size={16} />
          <div>{error}</div>
        </div>
      )}

      {/* ── Metrics Grid ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1.75rem' }}>
        <div className="card" style={{ background: 'var(--bg-card)' }}>
          <div className="flex items-center gap-2 mb-2" style={{ color: 'var(--text-tertiary)', fontSize: '0.78rem' }}>
            <FileText size={15} color="var(--accent-secondary)" /> Total Tracked
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--text-primary)' }}>
            {loading ? <div className="skeleton" style={{ height: 28, width: 40 }} /> : (stats?.applications_total ?? 0)}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', marginTop: '0.25rem' }}>
            All candidate applications
          </div>
        </div>

        <div className="card" style={{ background: 'var(--bg-card)' }}>
          <div className="flex items-center gap-2 mb-2" style={{ color: 'var(--text-tertiary)', fontSize: '0.78rem' }}>
            <Clock size={15} color="var(--accent-orange)" /> Awaiting Review
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--accent-orange)' }}>
            {loading ? <div className="skeleton" style={{ height: 28, width: 40 }} /> : (stats?.applications_awaiting_review ?? 0)}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', marginTop: '0.25rem' }}>
            Tailored resumes pending review
          </div>
        </div>

        <div className="card" style={{ background: 'var(--bg-card)' }}>
          <div className="flex items-center gap-2 mb-2" style={{ color: 'var(--text-tertiary)', fontSize: '0.78rem' }}>
            <CheckCircle2 size={15} color="var(--accent-green)" /> Submitted
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--accent-green)' }}>
            {loading ? <div className="skeleton" style={{ height: 28, width: 40 }} /> : (stats?.applications_submitted ?? 0)}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', marginTop: '0.25rem' }}>
            Confirmed submissions
          </div>
        </div>
      </div>

      {/* ── Applications Table / List Container ── */}
      <div className="card">
        <div className="flex items-center justify-between mb-4 pb-3" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
          <h3 style={{ fontSize: '1rem', color: 'var(--text-primary)' }}>Tracked Applications</h3>
          <span className="badge badge-gray" style={{ textTransform: 'none', fontSize: '0.72rem' }}>
            Full lifecycle tracking enabled in Phase 8
          </span>
        </div>

        {loading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', padding: '1rem 0' }}>
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="skeleton" style={{ height: 48, width: '100%', borderRadius: 'var(--radius-md)' }} />
            ))}
          </div>
        ) : (
          /* Empty State: Clear message when no applications exist (no fabricated records) */
          <div style={{ textAlign: 'center', padding: '4rem 1.5rem', color: 'var(--text-tertiary)' }}>
            <FileText size={48} style={{ margin: '0 auto 1rem', opacity: 0.35 }} />
            <h3 style={{ fontSize: '1.1rem', color: 'var(--text-secondary)' }}>No application records yet</h3>
            <p style={{ fontSize: '0.85rem', maxWidth: '440px', margin: '0.5rem auto 1.5rem', lineHeight: 1.6 }}>
              Applications appear here after you evaluate job matches and generate tailored resumes.
              Start by uploading your resume or exploring open startup positions.
            </p>
            <div className="flex justify-center gap-3">
              <Link href="/jobs" className="btn btn-primary btn-sm">
                <Briefcase size={13} /> Browse Open Roles
              </Link>
              <Link href="/onboarding" className="btn btn-secondary btn-sm">
                Upload Resume
              </Link>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
