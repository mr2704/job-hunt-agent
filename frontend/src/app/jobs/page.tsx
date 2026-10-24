'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Search, Filter, ExternalLink, ChevronLeft, ChevronRight,
  Briefcase, MapPin, Clock, Building2, Zap
} from 'lucide-react';
import AppShell from '@/components/AppShell';
import { api, type Job } from '@/lib/api';

const LEVELS = ['Fresher', 'Junior', 'Mid', 'Senior', 'Lead', 'Unspecified'];
const DEPARTMENTS = ['Engineering', 'Data & AI', 'Product', 'Design', 'Sales & Marketing', 'Operations', 'Other'];
const ATS_LIST = ['lever', 'greenhouse', 'workable', 'linkedin', 'naukri', 'wellfound', 'unknown'];

function levelColor(level: string | null): string {
  switch (level?.toLowerCase()) {
    case 'fresher': return 'badge-green';
    case 'junior':  return 'badge-cyan';
    case 'mid':     return 'badge-purple';
    case 'senior':  return 'badge-orange';
    case 'lead':    return 'badge-red';
    default:        return 'badge-gray';
  }
}

function CompanyAvatar({ name, logo }: { name: string; logo?: string | null }) {
  if (logo) return <div className="company-logo"><img src={logo} alt={name} /></div>;
  return (
    <div className="company-logo">
      {name.slice(0, 2).toUpperCase()}
    </div>
  );
}

function JobCard({ job, onClick }: { job: Job; onClick: () => void }) {
  const daysAgo = job.discovered_at
    ? Math.floor((Date.now() - new Date(job.discovered_at).getTime()) / 86400000)
    : null;

  return (
    <div className="job-card" onClick={onClick} id={`job-card-${job.id}`}>
      <div className="job-card-header">
        <CompanyAvatar name={job.company?.name ?? '?'} logo={job.company?.logo_url} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="job-title truncate">{job.title}</div>
          <div className="job-company">{job.company?.name ?? '—'}</div>
        </div>
        {job.application_url && (
          <a
            href={job.application_url}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-primary btn-sm"
            onClick={(e) => e.stopPropagation()}
            style={{ flexShrink: 0 }}
          >
            Apply <ExternalLink size={11} />
          </a>
        )}
      </div>

      <div className="job-tags">
        {job.level && <span className={`badge ${levelColor(job.level)}`}>{job.level}</span>}
        {job.department && <span className="badge badge-gray">{job.department}</span>}
        {job.employment_type && <span className="badge badge-cyan">{job.employment_type}</span>}
        {job.ats_platform && job.ats_platform !== 'unknown' && (
          <span className="badge badge-purple">{job.ats_platform}</span>
        )}
      </div>

      <div className="job-footer">
        <div className="job-meta">
          {job.location && <><MapPin size={11} />{job.location}</>}
          {daysAgo !== null && <><Clock size={11} />{daysAgo === 0 ? 'Today' : `${daysAgo}d ago`}</>}
        </div>
        {job.company?.sector && (
          <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>
            {job.company.sector}
          </span>
        )}
      </div>
    </div>
  );
}

function JobDetailPanel({ job, onClose }: { job: Job; onClose: () => void }) {
  return (
    <div style={{
      position: 'fixed',
      right: 0, top: 0, bottom: 0,
      width: '480px',
      background: 'var(--bg-card)',
      borderLeft: '1px solid var(--border-default)',
      overflowY: 'auto',
      zIndex: 200,
      padding: '1.5rem',
      boxShadow: '-8px 0 32px rgba(0,0,0,0.4)',
    }}>
      <div className="flex items-center justify-between mb-4">
        <h2 style={{ fontSize: '1.1rem' }}>Job Details</h2>
        <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
      </div>

      <div className="flex items-start gap-3 mb-4">
        <CompanyAvatar name={job.company?.name ?? '?'} logo={job.company?.logo_url} />
        <div>
          <h3 style={{ fontSize: '1rem', marginBottom: '0.2rem' }}>{job.title}</h3>
          <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>{job.company?.name}</div>
          {job.company?.website && (
            <a href={job.company.website} target="_blank" rel="noopener noreferrer" className="text-accent text-xs">
              {job.company.website.replace(/https?:\/\//, '')} <ExternalLink size={10} />
            </a>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        {job.level && <span className={`badge ${levelColor(job.level)}`}>{job.level}</span>}
        {job.department && <span className="badge badge-gray">{job.department}</span>}
        {job.employment_type && <span className="badge badge-cyan">{job.employment_type}</span>}
        {job.location && <span className="badge badge-gray"><MapPin size={10} />{job.location}</span>}
      </div>

      {job.description && (
        <div style={{ marginBottom: '1.25rem' }}>
          <h4 style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Description</h4>
          <p style={{ fontSize: '0.875rem', lineHeight: 1.7, whiteSpace: 'pre-wrap', color: 'var(--text-secondary)', maxHeight: 300, overflowY: 'auto' }}>
            {job.description}
          </p>
        </div>
      )}

      {job.required_skills && job.required_skills.length > 0 && (
        <div style={{ marginBottom: '1rem' }}>
          <h4 style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Required Skills</h4>
          <div className="flex flex-wrap gap-1">
            {job.required_skills.map(s => <span key={s} className="badge badge-purple">{s}</span>)}
          </div>
        </div>
      )}

      {job.preferred_skills && job.preferred_skills.length > 0 && (
        <div style={{ marginBottom: '1.25rem' }}>
          <h4 style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Preferred Skills</h4>
          <div className="flex flex-wrap gap-1">
            {job.preferred_skills.map(s => <span key={s} className="badge badge-gray">{s}</span>)}
          </div>
        </div>
      )}

      <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        <div style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>
          <strong>ATS Platform:</strong> {job.ats_platform ?? 'Unknown'}
        </div>
        <div style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>
          <strong>Source:</strong>{' '}
          {job.bsm_url && <a href={job.bsm_url} target="_blank" rel="noopener noreferrer" className="text-accent">BSM ↗</a>}
        </div>
        <div style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>
          <strong>Discovered:</strong> {new Date(job.discovered_at).toLocaleDateString()}
        </div>
      </div>

      {job.application_url && (
        <div style={{ marginTop: '1.5rem' }}>
          <a
            href={job.application_url}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-primary w-full"
            style={{ justifyContent: 'center' }}
          >
            Apply Now <ExternalLink size={14} />
          </a>
        </div>
      )}
    </div>
  );
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');
  const [level, setLevel] = useState('');
  const [dept, setDept] = useState('');
  const [selected, setSelected] = useState<Job | null>(null);
  const PAGE_SIZE = 24;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getJobs({ page, page_size: PAGE_SIZE, q, level, department: dept });
      setJobs(res.items);
      setTotal(res.total);
    } catch {
      setJobs([]);
    } finally {
      setLoading(false);
    }
  }, [page, q, level, dept]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setPage(1); }, [q, level, dept]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <AppShell>
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Jobs</h1>
          <p className="page-subtitle">
            {loading ? 'Loading…' : `${total.toLocaleString()} jobs discovered from Bangalore startups`}
          </p>
        </div>
      </div>

      {/* Search + filters */}
      <div style={{ marginBottom: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        <div className="search-bar">
          <Search size={16} color="var(--text-tertiary)" />
          <input
            placeholder="Search by title, company, skill…"
            value={q}
            onChange={e => setQ(e.target.value)}
            id="job-search-input"
          />
          {q && <button className="btn btn-ghost btn-sm" onClick={() => setQ('')} style={{ padding: '2px 6px' }}>✕</button>}
        </div>

        <div className="filter-row">
          <Filter size={13} color="var(--text-tertiary)" />
          {LEVELS.map(l => (
            <span
              key={l}
              className={`filter-chip ${level === l ? 'active' : ''}`}
              onClick={() => setLevel(level === l ? '' : l)}
              id={`filter-level-${l.toLowerCase()}`}
            >
              {l}
            </span>
          ))}
          <span style={{ width: '1px', height: '18px', background: 'var(--border-default)', margin: '0 0.25rem' }} />
          {DEPARTMENTS.map(d => (
            <span
              key={d}
              className={`filter-chip ${dept === d ? 'active' : ''}`}
              onClick={() => setDept(dept === d ? '' : d)}
              id={`filter-dept-${d.toLowerCase().replace(/\W+/g, '-')}`}
            >
              {d}
            </span>
          ))}
        </div>
      </div>

      {/* Job grid */}
      {loading ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1rem' }}>
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="job-card" style={{ cursor: 'default' }}>
              <div className="flex items-center gap-3 mb-3">
                <div className="skeleton" style={{ width: 40, height: 40, borderRadius: 'var(--radius-sm)' }} />
                <div style={{ flex: 1 }}>
                  <div className="skeleton mb-1" style={{ height: 16, width: '70%' }} />
                  <div className="skeleton" style={{ height: 12, width: '50%' }} />
                </div>
              </div>
              <div className="flex gap-2 mb-3">
                <div className="skeleton" style={{ width: 60, height: 20, borderRadius: 99 }} />
                <div className="skeleton" style={{ width: 80, height: 20, borderRadius: 99 }} />
              </div>
              <div className="skeleton" style={{ height: 12, width: '60%' }} />
            </div>
          ))}
        </div>
      ) : jobs.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '4rem 2rem', color: 'var(--text-tertiary)' }}>
          <Briefcase size={48} style={{ margin: '0 auto 1rem', opacity: 0.3 }} />
          <h3>No jobs found</h3>
          <p className="text-sm" style={{ marginTop: '0.5rem' }}>
            {q || level || dept
              ? 'Try clearing some filters.'
              : 'Run a discovery to find jobs from Bangalore startups.'}
          </p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1rem' }}>
          {jobs.map(j => <JobCard key={j.id} job={j} onClick={() => setSelected(j)} />)}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.75rem', marginTop: '2rem' }}>
          <button
            className="btn btn-secondary btn-sm"
            disabled={page <= 1}
            onClick={() => setPage(p => Math.max(1, p - 1))}
            id="pagination-prev"
          >
            <ChevronLeft size={14} /> Prev
          </button>
          <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
            Page {page} of {totalPages}
          </span>
          <button
            className="btn btn-secondary btn-sm"
            disabled={page >= totalPages}
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            id="pagination-next"
          >
            Next <ChevronRight size={14} />
          </button>
        </div>
      )}

      {/* Job detail panel */}
      {selected && <JobDetailPanel job={selected} onClose={() => setSelected(null)} />}
    </AppShell>
  );
}
