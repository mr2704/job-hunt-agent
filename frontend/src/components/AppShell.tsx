'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Briefcase,
  Building2,
  FileText,
  Settings,
  Search,
  ChevronRight,
  AlertCircle,
  CheckCircle2,
  Activity,
  Upload,
} from 'lucide-react';
import { api, type DashboardStats } from '@/lib/api';

const NAV = [
  {
    section: 'Overview',
    items: [
      { href: '/',          label: 'Dashboard',  icon: LayoutDashboard },
      { href: '/jobs',      label: 'Jobs',       icon: Briefcase,  badge: 'jobs' },
      { href: '/companies', label: 'Companies',  icon: Building2 },
    ],
  },
  {
    section: 'Candidate',
    items: [
      { href: '/onboarding', label: 'Resume & Profile', icon: Upload },
      { href: '/applications', label: 'Applications', icon: FileText },
    ],
  },
  {
    section: 'Tools',
    items: [
      { href: '/discovery', label: 'Discovery', icon: Search },
      { href: '/settings',  label: 'Settings',  icon: Settings },
    ],
  },
];

interface SidebarProps {
  stats: DashboardStats | null;
}

function Sidebar({ stats }: SidebarProps) {
  const pathname = usePathname();

  const getBadge = (key: string): string | null => {
    if (!stats) return null;
    if (key === 'jobs') return stats.open_jobs > 0 ? String(stats.open_jobs) : null;
    return null;
  };

  return (
    <aside className="sidebar">
      {/* Logo */}
      <div className="sidebar-logo">
        <div className="logo-mark">
          <div className="logo-icon">⚡</div>
          <div className="logo-text">
            JobAgent
            <span>AI-Powered</span>
          </div>
        </div>
      </div>

      {/* Profile status */}
      <div style={{ padding: '0 1rem', marginBottom: '0.5rem' }}>
        <div style={{
          background: stats?.has_confirmed_profile
            ? 'rgba(16,185,129,0.1)' : 'rgba(245,158,11,0.08)',
          border: `1px solid ${stats?.has_confirmed_profile
            ? 'rgba(16,185,129,0.3)' : 'rgba(245,158,11,0.25)'}`,
          borderRadius: 'var(--radius-md)',
          padding: '0.6rem 0.875rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          fontSize: '0.78rem',
        }}>
          {stats?.has_confirmed_profile
            ? <CheckCircle2 size={14} color="var(--accent-green)" />
            : <AlertCircle size={14} color="var(--accent-orange)" />}
          <span style={{ color: stats?.has_confirmed_profile ? 'var(--accent-green)' : 'var(--accent-orange)' }}>
            {stats?.has_confirmed_profile ? 'Profile confirmed' : 'No profile yet'}
          </span>
          {!stats?.has_confirmed_profile && (
            <Link href="/onboarding" style={{ marginLeft: 'auto', color: 'var(--accent-orange)', fontSize: '0.7rem' }}>
              Upload →
            </Link>
          )}
        </div>
      </div>

      {/* Navigation */}
      {NAV.map(({ section, items }) => (
        <div key={section} className="nav-section">
          <div className="nav-section-label">{section}</div>
          {items.map(({ href, label, icon: Icon, badge }) => {
            const isActive = pathname === href;
            const badgeVal = badge ? getBadge(badge) : null;
            return (
              <Link key={href} href={href} style={{ textDecoration: 'none' }}>
                <div className={`nav-item ${isActive ? 'active' : ''}`}>
                  <Icon className="nav-icon" size={16} />
                  {label}
                  {badgeVal && <span className="nav-badge">{badgeVal}</span>}
                  {isActive && <ChevronRight size={12} style={{ marginLeft: 'auto', opacity: 0.5 }} />}
                </div>
              </Link>
            );
          })}
        </div>
      ))}

      {/* Footer */}
      <div className="sidebar-footer">
        <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
          <Activity size={11} />
          {stats?.last_discovery_at
            ? `Last sync: ${new Date(stats.last_discovery_at).toLocaleDateString()}`
            : 'Not yet synced'}
        </div>
        <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', marginTop: '0.25rem' }}>
          v0.1.0 — Phase 1
        </div>
      </div>
    </aside>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [stats, setStats] = useState<DashboardStats | null>(null);

  useEffect(() => {
    let ignore = false;
    api.getDashboardStats().then((s) => {
      if (!ignore) setStats(s);
    }).catch(() => {});

    const interval = setInterval(() => {
      api.getDashboardStats().then((s) => {
        if (!ignore) setStats(s);
      }).catch(() => {});
    }, 30_000);

    return () => {
      ignore = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="app-shell">
      <Sidebar stats={stats} />
      <main className="main-content">
        {children}
      </main>
    </div>
  );
}
