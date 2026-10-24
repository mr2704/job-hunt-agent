'use client';

import { useState, useRef, useEffect, Fragment } from 'react';
import { Upload, CheckCircle2, AlertCircle, ChevronRight, Info, RefreshCw } from 'lucide-react';
import Link from 'next/link';
import AppShell from '@/components/AppShell';
import { api, type UploadResumeResponse } from '@/lib/api';

type Step = 'welcome' | 'upload' | 'review' | 'done';

const STEPS: { key: 'upload' | 'review'; label: string }[] = [
  { key: 'upload', label: 'Upload Resume' },
  { key: 'review', label: 'Review & Confirm' },
];

const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024; // 50 MB

function StepIndicator({ current }: { current: 'upload' | 'review' }) {
  const idx = STEPS.findIndex((s) => s.key === current);
  return (
    <div className="step-indicator">
      {STEPS.map((s, i) => (
        <Fragment key={s.key}>
          <div className={`step ${i < idx ? 'done' : i === idx ? 'active' : ''}`}>
            {i < idx ? '✓' : i + 1}
          </div>
          {i < STEPS.length - 1 && <div className="step-line" />}
        </Fragment>
      ))}
    </div>
  );
}

function WelcomeScreen({ onStart }: { onStart: () => void }) {
  return (
    <div className="onboarding-card">
      <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
        <div
          style={{
            width: 80,
            height: 80,
            background: 'var(--gradient-brand)',
            borderRadius: 'var(--radius-xl)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 1.5rem',
            fontSize: '2rem',
            boxShadow: 'var(--shadow-glow)',
          }}
        >
          ⚡
        </div>
        <h1 style={{ marginBottom: '0.75rem' }}>AI Job Discovery Agent</h1>
        <p style={{ color: 'var(--text-secondary)', maxWidth: 480, margin: '0 auto' }}>
          This agent discovers open roles at Bangalore startups, evaluates your eligibility,
          tailors your resume, and tracks your applications — without any manual work.
        </p>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '1rem',
          marginBottom: '2rem',
        }}
      >
        {[
          { icon: '🔍', title: 'Job Discovery', desc: 'Crawls Bangalore Startup Map for open roles' },
          {
            icon: '📋',
            title: 'Eligibility Check',
            desc: "Evaluates each job's requirements against your profile",
          },
          { icon: '📝', title: 'Resume Tailoring', desc: 'Adapts your LaTeX resume for each role' },
          { icon: '📊', title: 'Application Tracker', desc: 'Tracks status, interviews, and outcomes' },
        ].map(({ icon, title, desc }) => (
          <div key={title} className="card" style={{ padding: '1rem' }}>
            <div style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>{icon}</div>
            <h4 style={{ fontSize: '0.9rem', marginBottom: '0.25rem' }}>{title}</h4>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>{desc}</p>
          </div>
        ))}
      </div>

      <div className="alert alert-info mb-4">
        <Info size={16} />
        <div>
          <strong>Job discovery works without a profile.</strong> You can browse jobs right now.
          Upload your resume to enable personalized matching, eligibility evaluation, and resume
          tailoring.
        </div>
      </div>

      <div style={{ display: 'flex', gap: '0.75rem' }}>
        <button
          className="btn btn-primary"
          onClick={onStart}
          style={{ flex: 1, justifyContent: 'center' }}
          id="start-onboarding"
        >
          Upload My Resume <ChevronRight size={16} />
        </button>
        <Link
          href="/jobs"
          className="btn btn-secondary"
          style={{ flex: 1, justifyContent: 'center', textDecoration: 'none' }}
        >
          Browse Jobs First
        </Link>
      </div>
    </div>
  );
}

function UploadStep({
  onUploaded,
}: {
  onUploaded: (data: UploadResumeResponse) => void;
}) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = async (file: File) => {
    if (uploading) return;

    if (!file) {
      setError('Please select a file to upload.');
      return;
    }

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Only PDF files are accepted for resume upload.');
      return;
    }

    if (file.size === 0) {
      setError('The selected file is empty. Please upload a valid PDF resume.');
      return;
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      setError('File exceeds maximum size of 50 MB.');
      return;
    }

    setUploading(true);
    setError(null);

    try {
      const result = await api.uploadResume(file);
      onUploaded(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setUploading(false);
    }
  };

  const handleZoneClick = () => {
    if (!uploading) {
      inputRef.current?.click();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleZoneClick();
    }
  };

  return (
    <div className="onboarding-card">
      <StepIndicator current="upload" />
      <h2 style={{ marginBottom: '0.5rem' }}>Upload Your Resume</h2>
      <p className="text-muted mb-6" style={{ fontSize: '0.9rem' }}>
        Upload your base resume PDF. We will extract your details and show them for review.
        Nothing is confirmed until you explicitly approve it.
      </p>

      <div
        className={`upload-zone ${dragging ? 'dragover' : ''}`}
        onClick={handleZoneClick}
        onKeyDown={handleKeyDown}
        role="button"
        tabIndex={0}
        aria-label="Upload resume PDF zone. Press Enter or Space to choose a file."
        aria-disabled={uploading}
        onDragOver={(e) => {
          e.preventDefault();
          if (!uploading) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          if (uploading) return;
          const f = e.dataTransfer.files?.[0];
          if (f) handleFile(f);
        }}
        id="resume-upload-zone"
        style={{ cursor: uploading ? 'not-allowed' : 'pointer', opacity: uploading ? 0.7 : 1 }}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,application/pdf"
          style={{ display: 'none' }}
          disabled={uploading}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleFile(f);
            // Reset input so selecting the identical file again triggers onChange
            e.target.value = '';
          }}
          id="resume-file-input"
        />
        <div className="upload-icon">
          {uploading ? (
            <div className="spinner" />
          ) : (
            <Upload size={24} color="var(--accent-primary)" />
          )}
        </div>
        <h3 style={{ marginBottom: '0.5rem' }}>
          {uploading ? 'Uploading and parsing…' : 'Drop your PDF here'}
        </h3>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-tertiary)' }}>
          or click to browse · PDF only · max 50MB
        </p>
      </div>

      {error && (
        <div className="alert alert-error mt-4" role="alert">
          <AlertCircle size={14} /> <span>{error}</span>
        </div>
      )}

      <div className="alert alert-info mt-4">
        <Info size={14} />
        <p style={{ fontSize: '0.8rem' }}>
          Your resume is stored locally on this server only. Personal data is never sent to third
          parties without your approval.
        </p>
      </div>
    </div>
  );
}

function ReviewStep({
  extracted,
  profileId,
  onConfirmed,
  onReupload,
}: {
  extracted: Record<string, unknown>;
  profileId: string;
  onConfirmed: () => void;
  onReupload: () => void;
}) {
  const [fields, setFields] = useState({
    full_name: (extracted.full_name as string) ?? '',
    email: (extracted.email as string) ?? '',
    phone: (extracted.phone as string) ?? '',
    location: (extracted.location as string) ?? '',
    degree: (extracted.degree as string) ?? '',
    graduation_year: extracted.graduation_year != null ? String(extracted.graduation_year) : '',
    cgpa: extracted.cgpa != null ? String(extracted.cgpa) : '',
    cgpa_scale: extracted.cgpa_scale != null ? String(extracted.cgpa_scale) : '',
    skills: Array.isArray(extracted.skills) ? (extracted.skills as string[]).join(', ') : '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const warnings: string[] = (extracted._warnings as string[]) ?? [];

  const validateForm = (): string | null => {
    const emailTrim = fields.email.trim();
    if (emailTrim && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailTrim)) {
      return 'Please enter a valid email address (e.g. candidate@example.com).';
    }

    const gradYearTrim = fields.graduation_year.trim();
    if (gradYearTrim) {
      const yr = Number(gradYearTrim);
      if (!Number.isInteger(yr) || yr < 1970 || yr > 2035) {
        return 'Graduation year must be a valid 4-digit year between 1970 and 2035.';
      }
    }

    const cgpaTrim = fields.cgpa.trim();
    const scaleTrim = fields.cgpa_scale.trim();

    if (cgpaTrim) {
      const cgpaVal = Number(cgpaTrim);
      if (Number.isNaN(cgpaVal) || !Number.isFinite(cgpaVal) || cgpaVal < 0) {
        return 'CGPA must be a valid non-negative number.';
      }
      if (!scaleTrim) {
        return 'Please specify the CGPA scale (e.g. 10.0 or 4.0) for your CGPA.';
      }
    }

    if (scaleTrim) {
      const scaleVal = Number(scaleTrim);
      if (Number.isNaN(scaleVal) || !Number.isFinite(scaleVal) || scaleVal <= 0) {
        return 'CGPA scale must be a positive number (e.g. 10.0 or 4.0).';
      }
      if (cgpaTrim) {
        const cgpaVal = Number(cgpaTrim);
        if (cgpaVal > scaleVal) {
          return `CGPA (${cgpaVal}) cannot exceed the stated scale of ${scaleVal}.`;
        }
      }
    }

    return null;
  };

  const handleConfirm = async () => {
    if (saving) return;

    const validationError = validateForm();
    if (validationError) {
      setError(validationError);
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const normalizedSkills = fields.skills
        ? Array.from(
            new Set(
              fields.skills
                .split(',')
                .map((s) => s.trim())
                .filter(Boolean)
            )
          )
        : undefined;

      // Save edits scoped to the current profileId
      await api.updateProfile(
        {
          full_name: fields.full_name.trim() || undefined,
          email: fields.email.trim() || undefined,
          phone: fields.phone.trim() || undefined,
          location: fields.location.trim() || undefined,
          degree: fields.degree.trim() || undefined,
          graduation_year: fields.graduation_year.trim()
            ? Number(fields.graduation_year.trim())
            : undefined,
          cgpa: fields.cgpa.trim() ? Number(fields.cgpa.trim()) : undefined,
          cgpa_scale: fields.cgpa_scale.trim() ? Number(fields.cgpa_scale.trim()) : undefined,
          skills: normalizedSkills,
        },
        profileId
      );

      // Confirm scoped to the current profileId
      await api.confirmProfile(profileId);
      onConfirmed();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="onboarding-card">
      <StepIndicator current="review" />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
        <h2>Review Extracted Profile</h2>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={onReupload}
          disabled={saving}
          style={{ fontSize: '0.8rem' }}
        >
          <RefreshCw size={12} /> Upload different PDF
        </button>
      </div>
      <p className="text-muted mb-4" style={{ fontSize: '0.9rem' }}>
        Review and edit your extracted details below. Your profile remains in draft and
        personalized matching is not enabled until you confirm.
      </p>

      {warnings.length > 0 && (
        <div className="alert alert-warning mb-4" role="alert">
          <AlertCircle size={14} />
          <div>
            {warnings.map((w, i) => (
              <div key={i} style={{ fontSize: '0.8rem' }}>
                {w}
              </div>
            ))}
          </div>
        </div>
      )}

      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '0.875rem',
          marginBottom: '1.5rem',
        }}
      >
        {(
          [
            { key: 'full_name', label: 'Full Name', type: 'text' },
            { key: 'email', label: 'Email', type: 'email' },
            { key: 'phone', label: 'Phone', type: 'text' },
            {
              key: 'location',
              label: 'Current Location',
              type: 'text',
              placeholder: 'e.g. Bangalore, Karnataka',
            },
            { key: 'degree', label: 'Degree', type: 'text' },
            {
              key: 'graduation_year',
              label: 'Graduation Year',
              type: 'number',
              placeholder: 'e.g. 2024',
            },
            { key: 'cgpa', label: 'CGPA', type: 'number', step: '0.01' },
            {
              key: 'cgpa_scale',
              label: 'CGPA Scale',
              type: 'number',
              placeholder: '10.0 or 4.0',
            },
            { key: 'skills', label: 'Skills (comma-separated)', type: 'text' },
          ] as Array<{
            key: keyof typeof fields;
            label: string;
            type: string;
            placeholder?: string;
            step?: string;
          }>
        ).map(({ key, label, type, placeholder, step }) => (
          <div key={key}>
            <label
              htmlFor={`profile-field-${key}`}
              style={{
                display: 'block',
                fontSize: '0.8rem',
                color: 'var(--text-tertiary)',
                marginBottom: '0.3rem',
                fontWeight: 600,
              }}
            >
              {label}
            </label>
            <input
              id={`profile-field-${key}`}
              type={type}
              step={step}
              placeholder={placeholder ?? label}
              value={String(fields[key] ?? '')}
              onChange={(e) => setFields((f) => ({ ...f, [key]: e.target.value }))}
              style={{
                width: '100%',
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border-default)',
                borderRadius: 'var(--radius-md)',
                padding: '0.6rem 0.875rem',
                color: 'var(--text-primary)',
                fontSize: '0.9rem',
                fontFamily: 'var(--font-sans)',
                outline: 'none',
                transition: 'var(--transition-fast)',
              }}
              onFocus={(e) => (e.target.style.borderColor = 'var(--accent-primary)')}
              onBlur={(e) => (e.target.style.borderColor = 'var(--border-default)')}
            />
          </div>
        ))}
      </div>

      <div className="alert alert-warning mb-4">
        <AlertCircle size={14} />
        <p style={{ fontSize: '0.8rem' }}>
          <strong>Important:</strong> Only enter information that is true and accurate. The agent
          will never fabricate or infer qualifications on your behalf.
        </p>
      </div>

      {error && (
        <div className="alert alert-error mb-4" role="alert">
          <AlertCircle size={14} /> <span>{error}</span>
        </div>
      )}

      <button
        className="btn btn-primary"
        onClick={handleConfirm}
        disabled={saving}
        style={{ width: '100%', justifyContent: 'center' }}
        id="confirm-profile-btn"
      >
        {saving ? (
          <>
            <div className="spinner" style={{ width: 14, height: 14 }} />
            Saving…
          </>
        ) : (
          <>
            <CheckCircle2 size={16} />
            Confirm Profile & Enable Matching
          </>
        )}
      </button>
    </div>
  );
}

function DoneStep() {
  return (
    <div className="onboarding-card" style={{ textAlign: 'center' }}>
      <div
        style={{
          width: 72,
          height: 72,
          background: 'rgba(16,185,129,0.15)',
          border: '2px solid var(--accent-green)',
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto 1.5rem',
          fontSize: '2rem',
        }}
      >
        ✓
      </div>
      <h2 style={{ marginBottom: '0.5rem' }}>Profile Confirmed!</h2>
      <p className="text-muted mb-6">
        Personalized eligibility evaluation and match scoring are now enabled.
      </p>
      <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
        <Link href="/jobs" className="btn btn-primary" style={{ textDecoration: 'none' }}>
          Browse Matched Jobs →
        </Link>
        <Link href="/" className="btn btn-secondary" style={{ textDecoration: 'none' }}>
          Dashboard
        </Link>
      </div>
    </div>
  );
}

export default function OnboardingPage() {
  const [step, setStep] = useState<Step>('welcome');
  const [uploadResult, setUploadResult] = useState<UploadResumeResponse | null>(null);

  // Safely check if a profile already exists on initial mount
  useEffect(() => {
    let active = true;
    api
      .getProfile()
      .then((profile) => {
        if (!active || !profile) return;
        if (profile.is_confirmed) {
          setStep('done');
        } else {
          // Recover draft profile for review without automatically confirming it
          setUploadResult({
            message: 'Draft profile recovered',
            profile_id: profile.id,
            extracted: profile as unknown as Record<string, unknown>,
          });
          setStep('review');
        }
      })
      .catch(() => {
        // Silently remain on default welcome step if backend is unreachable
      });

    return () => {
      active = false;
    };
  }, []);

  return (
    <AppShell>
      <div style={{ maxWidth: 700, margin: '2rem auto', padding: '0 1rem' }}>
        {step === 'welcome' && <WelcomeScreen onStart={() => setStep('upload')} />}

        {step === 'upload' && (
          <UploadStep
            onUploaded={(data) => {
              setUploadResult(data);
              setStep('review');
            }}
          />
        )}

        {step === 'review' && uploadResult && (
          <ReviewStep
            extracted={uploadResult.extracted}
            profileId={uploadResult.profile_id}
            onConfirmed={() => setStep('done')}
            onReupload={() => setStep('upload')}
          />
        )}

        {step === 'done' && <DoneStep />}
      </div>
    </AppShell>
  );
}
