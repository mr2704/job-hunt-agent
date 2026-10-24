/**
 * API client for the job discovery agent backend.
 * Base URL is configured via environment variable NEXT_PUBLIC_API_URL.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const API  = `${BASE}/api/v1`;

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

// ── Types (mirrors backend Pydantic schemas) ──────────────────────────────

export interface Company {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  sector: string | null;
  area: string | null;
  founded_year: number | null;
  website: string | null;
  logo_url: string | null;
  funding_stage: string | null;
  bsm_url: string | null;
  is_active: boolean;
  discovered_at: string;
  last_verified_at: string | null;
}

export interface Job {
  id: string;
  company_id: string;
  title: string;
  department: string | null;
  level: string | null;
  employment_type: string | null;
  location: string | null;
  remote_policy: string | null;
  description: string | null;
  required_skills: string[] | null;
  preferred_skills: string[] | null;
  experience_min_years: number | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  bsm_url: string | null;
  original_url: string | null;
  application_url: string | null;
  ats_platform: string | null;
  posted_at: string | null;
  discovered_at: string;
  last_verified_at: string | null;
  status: string;
  extraction_confidence: number | null;
  company?: Company;
}

export interface PagedResponse<T> {
  total: number;
  page: number;
  page_size: number;
  items: T[];
}

export interface DashboardStats {
  total_companies: number;
  total_jobs: number;
  open_jobs: number;
  eligible_jobs: number;
  high_match_jobs: number;
  applications_awaiting_review: number;
  applications_submitted: number;
  applications_total: number;
  has_confirmed_profile: boolean;
  last_discovery_at: string | null;
}

export interface CandidateProfile {
  id: string;
  version: number;
  full_name: string | null;
  email: string | null;
  phone: string | null;
  location: string | null;
  degree: string | null;
  graduation_year: number | null;
  cgpa: number | null;
  cgpa_scale: number | null;
  skills: string[] | null;
  is_confirmed: boolean;
  confirmed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface UploadResumeResponse {
  message: string;
  profile_id: string;
  extracted: Record<string, unknown>;
  warnings?: string[];
  next_step?: string;
}

// ── API functions ─────────────────────────────────────────────────────────

export const api = {
  // Dashboard
  getDashboardStats: () => request<DashboardStats>('/dashboard/stats'),

  // Jobs
  getJobs: (params?: {
    page?: number;
    page_size?: number;
    q?: string;
    level?: string;
    department?: string;
    status?: string;
  }) => {
    const qs = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') qs.set(k, String(v));
      });
    }
    return request<PagedResponse<Job>>(`/jobs?${qs}`);
  },

  getJob: (id: string) => request<Job>(`/jobs/${id}`),

  // Companies
  getCompanies: (params?: { page?: number; q?: string }) => {
    const qs = new URLSearchParams();
    if (params) Object.entries(params).forEach(([k, v]) => v && qs.set(k, String(v)));
    return request<PagedResponse<Company>>(`/companies?${qs}`);
  },

  // Discovery
  triggerDiscovery: (body: { max_companies?: number; fetch_jd?: boolean }) =>
    request<{ status: string; stats: Record<string, number> }>('/discovery/run', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getDiscoveryStatus: () => request<Record<string, unknown>>('/discovery/status'),

  // Candidate
  getProfile: (profileId?: string) => {
    const qs = profileId ? `?profile_id=${encodeURIComponent(profileId)}` : '';
    return request<CandidateProfile | null>(`/candidate/profile${qs}`);
  },

  uploadResume: async (file: File): Promise<UploadResumeResponse> => {
    const form = new FormData();
    form.append('file', file);

    let res: Response;
    try {
      res = await fetch(`${API}/candidate/resume/upload`, {
        method: 'POST',
        body: form,
      });
    } catch {
      throw new Error('Network error: Unable to connect to server. Please check your connection.');
    }

    let data: unknown;
    try {
      data = await res.json();
    } catch {
      throw new Error(`Server returned an invalid response (HTTP ${res.status}).`);
    }

    if (!res.ok) {
      const payload = data as { detail?: string | Array<{ msg?: string }> };
      const detail = payload?.detail;
      const message =
        typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
            ? detail.map((d) => d.msg || JSON.stringify(d)).join(', ')
            : `Upload failed (HTTP ${res.status})`;
      throw new Error(message);
    }

    const typedData = data as Record<string, unknown>;
    if (!typedData || typeof typedData !== 'object') {
      throw new Error('Received an invalid response payload from the server.');
    }
    if (!typedData.profile_id || typeof typedData.profile_id !== 'string') {
      throw new Error('Upload response is missing candidate profile identifier.');
    }
    if (!typedData.extracted || typeof typedData.extracted !== 'object') {
      throw new Error('Upload response is missing extracted profile data.');
    }

    return typedData as unknown as UploadResumeResponse;
  },

  updateProfile: (data: Partial<CandidateProfile>, profileId?: string) => {
    const qs = profileId ? `?profile_id=${encodeURIComponent(profileId)}` : '';
    return request<CandidateProfile>(`/candidate/profile${qs}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  confirmProfile: (profileId?: string) => {
    const qs = profileId ? `?profile_id=${encodeURIComponent(profileId)}` : '';
    return request<{ message: string; profile_id: string; version?: number }>(
      `/candidate/profile/confirm${qs}`,
      {
        method: 'POST',
      }
    );
  },

  // Health
  health: () => request<{ status: string }>('/health').catch(() => null),
};

