'use client';

import { useState, useEffect } from 'react';
import {
  Building2, Search, ExternalLink, ChevronLeft, ChevronRight,
  MapPin, Calendar, DollarSign, Globe
} from 'lucide-react';
import AppShell from '@/components/AppShell';
import { api, type Company } from '@/lib/api';

function CompanyLogo({ name, logo }: { name: string; logo?: string | null }) {
  if (logo) {
    return (
      <div className="company-logo">
        <img src={logo} alt={name} />
      </div>
    );
  }
  return (
    <div className="company-logo">
      {name.slice(0, 2).toUpperCase()}
    </div>
  );
}

export default function CompaniesPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState('');
  const PAGE_SIZE = 24;

  const currentKey = `${page}|${q}`;
  const [loadedKey, setLoadedKey] = useState<string | null>(null);
  const loading = loadedKey !== currentKey;

  useEffect(() => {
    let ignore = false;
    const reqKey = `${page}|${q}`;
    api.getCompanies({ page, q: q || undefined })
      .then((res) => {
        if (!ignore) {
          setCompanies(res.items);
          setTotal(res.total);
          setLoadedKey(reqKey);
        }
      })
      .catch(() => {
        if (!ignore) {
          setCompanies([]);
          setLoadedKey(reqKey);
        }
      });

    return () => {
      ignore = true;
    };
  }, [page, q]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <AppShell>
      {/* ── Page Header ── */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Companies</h1>
          <p className="page-subtitle">
            {loading ? 'Loading…' : `${total.toLocaleString()} Bangalore startups and tech companies`}
          </p>
        </div>
      </div>

      {/* ── Search Bar ── */}
      <div style={{ marginBottom: '1.25rem' }}>
        <div className="search-bar">
          <Search size={16} color="var(--text-tertiary)" />
          <input
            placeholder="Search companies by name..."
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
            id="company-search-input"
          />
          {q && (
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => {
                setQ('');
                setPage(1);
              }}
              style={{ padding: '2px 6px' }}
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* ── Companies Grid ── */}
      {loading ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1rem' }}>
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="card" style={{ cursor: 'default' }}>
              <div className="flex items-center gap-3 mb-3">
                <div className="skeleton" style={{ width: 40, height: 40, borderRadius: 'var(--radius-sm)' }} />
                <div style={{ flex: 1 }}>
                  <div className="skeleton mb-1" style={{ height: 16, width: '65%' }} />
                  <div className="skeleton" style={{ height: 12, width: '40%' }} />
                </div>
              </div>
              <div className="skeleton mb-2" style={{ height: 12, width: '90%' }} />
              <div className="skeleton" style={{ height: 12, width: '75%' }} />
            </div>
          ))}
        </div>
      ) : companies.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '4rem 2rem', color: 'var(--text-tertiary)' }}>
          <Building2 size={48} style={{ margin: '0 auto 1rem', opacity: 0.3 }} />
          <h3>No companies found</h3>
          <p className="text-sm" style={{ marginTop: '0.5rem' }}>
            {q ? 'Try clearing your search term.' : 'Run job discovery to crawl Bangalore startup companies.'}
          </p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1rem' }}>
          {companies.map((c) => (
            <div key={c.id} className="card" id={`company-card-${c.id}`} style={{ display: 'flex', flexDirection: 'column' }}>
              <div className="flex items-start gap-3 mb-3">
                <CompanyLogo name={c.name} logo={c.logo_url} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="job-title truncate">{c.name}</div>
                  {c.sector && <div className="job-company truncate">{c.sector}</div>}
                </div>
              </div>

              {c.description && (
                <p className="text-sm text-secondary truncate mb-3" style={{ maxHeight: '2.8rem', overflow: 'hidden' }}>
                  {c.description}
                </p>
              )}

              <div className="flex flex-wrap gap-2 mb-3 mt-auto">
                {c.area && (
                  <span className="badge badge-gray" style={{ textTransform: 'none' }}>
                    <MapPin size={10} /> {c.area}
                  </span>
                )}
                {c.founded_year && (
                  <span className="badge badge-gray" style={{ textTransform: 'none' }}>
                    <Calendar size={10} /> Founded {c.founded_year}
                  </span>
                )}
                {c.funding_stage && (
                  <span className="badge badge-cyan" style={{ textTransform: 'none' }}>
                    <DollarSign size={10} /> {c.funding_stage}
                  </span>
                )}
              </div>

              <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '0.75rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.78rem' }}>
                <div className="flex items-center gap-3">
                  {c.website && (
                    <a
                      href={c.website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-accent flex items-center gap-1"
                    >
                      <Globe size={11} /> Website <ExternalLink size={10} />
                    </a>
                  )}
                  {c.bsm_url && (
                    <a
                      href={c.bsm_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-muted flex items-center gap-1"
                    >
                      BSM ↗
                    </a>
                  )}
                </div>
                <span style={{ color: 'var(--text-tertiary)', fontSize: '0.72rem' }}>
                  {new Date(c.discovered_at).toLocaleDateString()}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Pagination ── */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.75rem', marginTop: '2rem' }}>
          <button
            className="btn btn-secondary btn-sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            id="company-pagination-prev"
          >
            <ChevronLeft size={14} /> Prev
          </button>
          <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
            Page {page} of {totalPages}
          </span>
          <button
            className="btn btn-secondary btn-sm"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            id="company-pagination-next"
          >
            Next <ChevronRight size={14} />
          </button>
        </div>
      )}
    </AppShell>
  );
}
