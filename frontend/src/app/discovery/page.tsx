'use client';

import { useState, useEffect, useRef } from 'react';
import {
  Search, Play, RefreshCw, AlertCircle, CheckCircle2,
  Building2, Briefcase, Clock, AlertTriangle, ArrowRight
} from 'lucide-react';
import AppShell from '@/components/AppShell';
import { api } from '@/lib/api';
import Link from 'next/link';

interface DiscoveryStats {
  companies_found?: number;
  jobs_found?: number;
  errors?: number;
  [key: string]: unknown;
}

export default function DiscoveryPage() {
  const [running, setRunning] = useState(false);
  const [lastStats, setLastStats] = useState<DiscoveryStats | null>(null);
  const [statusText, setStatusText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [maxCompanies, setMaxCompanies] = useState<number>(20);
  const [fetchJd, setFetchJd] = useState<boolean>(false);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Load initial status on mount
  useEffect(() => {
    let ignore = false;
    api.getDiscoveryStatus()
      .then((res) => {
        if (!ignore && res && typeof res === 'object') {
          if (res.status === 'no_run_yet') {
            setStatusText('No discovery run recorded yet.');
          } else {
            setLastStats(res as DiscoveryStats);
          }
        }
      })
      .catch(() => {});

    return () => {
      ignore = true;
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, []);

  const startDiscovery = async () => {
    if (running) return;

    setRunning(true);
    setError(null);
    setStatusText('Initiating discovery crawl...');

    // Poll status while in-flight
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    pollIntervalRef.current = setInterval(() => {
      api.getDiscoveryStatus()
        .then((s) => {
          if (s && typeof s === 'object' && s.status !== 'no_run_yet') {
            setLastStats(s as DiscoveryStats);
          }
        })
        .catch(() => {});
    }, 2000);

    try {
      const response = await api.triggerDiscovery({
        max_companies: maxCompanies,
        fetch_jd: fetchJd,
      });

      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }

      setLastStats(response.stats as DiscoveryStats);
      setStatusText(response.status);
    } catch (err: unknown) {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
      const msg = err instanceof Error ? err.message : 'Discovery run failed. Please verify backend connectivity.';
      setError(msg);
    } finally {
      setRunning(false);
    }
  };

  const companiesCount = typeof lastStats?.companies_found === 'number' ? lastStats.companies_found : 0;
  const jobsCount = typeof lastStats?.jobs_found === 'number' ? lastStats.jobs_found : 0;
  const errorCount = typeof lastStats?.errors === 'number' ? lastStats.errors : 0;
  const hasExtractedRecords = companiesCount > 0 || jobsCount > 0;
  const hasFinishedRun = lastStats !== null && !running;

  return (
    <AppShell>
      {/* ── Page Header ── */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Job Discovery</h1>
          <p className="page-subtitle">
            Crawl and extract active startup opportunities across Bangalore tech hubs
          </p>
        </div>
      </div>

      {/* ── Error Banner ── */}
      {error && (
        <div className="alert alert-error mb-4">
          <AlertCircle size={16} />
          <div>
            <strong>Discovery Error:</strong> {error}
          </div>
        </div>
      )}

      {/* ── Configuration & Execution Card ── */}
      <div className="card mb-6">
        <h3 style={{ fontSize: '1.05rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Search size={18} color="var(--accent-secondary)" /> Discovery Crawler Controls
        </h3>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.25rem', marginBottom: '1.5rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
              Maximum Companies to Scan
            </label>
            <input
              type="number"
              min={1}
              max={500}
              value={maxCompanies}
              disabled={running}
              onChange={(e) => setMaxCompanies(Math.max(1, parseInt(e.target.value, 10) || 1))}
              style={{
                width: '100%',
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border-default)',
                borderRadius: 'var(--radius-md)',
                padding: '0.625rem 0.875rem',
                color: 'var(--text-primary)',
                fontSize: '0.9rem',
              }}
            />
            <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', marginTop: '0.25rem' }}>
              Limits depth per crawl run
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
              Deep Description Extraction
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', marginTop: '0.5rem' }}>
              <input
                type="checkbox"
                checked={fetchJd}
                disabled={running}
                onChange={(e) => setFetchJd(e.target.checked)}
                style={{ width: '16px', height: '16px', accentColor: 'var(--accent-primary)' }}
              />
              <span style={{ fontSize: '0.875rem', color: 'var(--text-primary)' }}>Fetch full job descriptions</span>
            </label>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', marginTop: '0.25rem' }}>
              Fetches full ATS postings for richer keyword analysis
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            className="btn btn-primary"
            onClick={startDiscovery}
            disabled={running}
            id="start-discovery-btn"
          >
            {running ? (
              <>
                <div className="spinner" style={{ width: 14, height: 14 }} />
                <span>Running Discovery Crawl...</span>
              </>
            ) : (
              <>
                <Play size={14} />
                <span>Start Discovery</span>
              </>
            )}
          </button>

          {running ? (
            <div style={{ fontSize: '0.82rem', color: 'var(--accent-secondary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <RefreshCw size={13} className="spinner" />
              <span>{statusText ?? 'Crawl in progress — polling status from backend...'}</span>
            </div>
          ) : statusText ? (
            <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>
              {statusText}
            </div>
          ) : null}
        </div>
      </div>

      {/* ── Status & Outcome State ── */}
      {hasFinishedRun && (
        <div className="mb-6">
          {hasExtractedRecords ? (
            /* Genuine Success with Extracted Records */
            <div className="card" style={{ borderColor: 'rgba(16,185,129,0.3)', background: 'rgba(16,185,129,0.03)' }}>
              <div className="flex items-center gap-2 mb-4">
                <CheckCircle2 size={18} color="var(--accent-green)" />
                <h3 style={{ fontSize: '1rem', color: 'var(--accent-green)' }}>Discovery Run Completed</h3>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '1rem' }}>
                <div className="card" style={{ background: 'var(--bg-elevated)', padding: '0.875rem' }}>
                  <div className="flex items-center gap-2 mb-1" style={{ color: 'var(--text-tertiary)', fontSize: '0.75rem' }}>
                    <Building2 size={13} /> Companies Found
                  </div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--accent-primary)' }}>
                    {companiesCount}
                  </div>
                </div>

                <div className="card" style={{ background: 'var(--bg-elevated)', padding: '0.875rem' }}>
                  <div className="flex items-center gap-2 mb-1" style={{ color: 'var(--text-tertiary)', fontSize: '0.75rem' }}>
                    <Briefcase size={13} /> Jobs Discovered
                  </div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--accent-green)' }}>
                    {jobsCount}
                  </div>
                </div>

                <div className="card" style={{ background: 'var(--bg-elevated)', padding: '0.875rem' }}>
                  <div className="flex items-center gap-2 mb-1" style={{ color: 'var(--text-tertiary)', fontSize: '0.75rem' }}>
                    <AlertTriangle size={13} /> Extraction Errors
                  </div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 800, color: errorCount > 0 ? 'var(--accent-orange)' : 'var(--text-secondary)' }}>
                    {errorCount}
                  </div>
                </div>
              </div>

              <div className="mt-4 flex gap-3">
                <Link href="/jobs" className="btn btn-secondary btn-sm">
                  Browse Discovered Jobs <ArrowRight size={13} />
                </Link>
                <Link href="/companies" className="btn btn-ghost btn-sm">
                  Browse Companies
                </Link>
              </div>
            </div>
          ) : (
            /* Completed with Zero Records Extracted (Issue B/C) */
            <div className="card" style={{ borderColor: 'rgba(245,158,11,0.3)', background: 'rgba(245,158,11,0.04)' }}>
              <div className="flex items-start gap-3">
                <AlertTriangle size={20} color="var(--accent-orange)" style={{ flexShrink: 0, marginTop: '2px' }} />
                <div>
                  <h3 style={{ fontSize: '1rem', color: 'var(--accent-orange)', marginBottom: '0.35rem' }}>
                    Completed, but no records were extracted
                  </h3>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: '0.75rem' }}>
                    The crawler completed execution against Bangalore Startup Map, but returned 0 hiring companies and 0 jobs.
                    This occurs when the external source page does not contain standard Next.js embedded data (<code>__NEXT_DATA__</code>)
                    or when the listings structure has changed. Discovery pipeline repair is scheduled in Phase 5.
                  </p>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                    Reported metrics: companies_found={companiesCount}, jobs_found={jobsCount}, errors={errorCount}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Empty State before first run ── */}
      {!hasFinishedRun && !running && (
        <div style={{ textAlign: 'center', padding: '3.5rem 1.5rem', color: 'var(--text-tertiary)', background: 'var(--bg-card)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-default)' }}>
          <Clock size={40} style={{ margin: '0 auto 0.75rem', opacity: 0.4 }} />
          <h3 style={{ fontSize: '1.05rem', color: 'var(--text-secondary)' }}>Ready to run discovery</h3>
          <p style={{ fontSize: '0.85rem', marginTop: '0.25rem', maxWidth: '420px', margin: '0.5rem auto 1.25rem' }}>
            Click &quot;Start Discovery&quot; above to scan Bangalore startup job listings and populate the database.
          </p>
        </div>
      )}
    </AppShell>
  );
}
