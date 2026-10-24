import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'AI Job Discovery Agent — Bangalore Startups',
  description:
    'Discover entry-level jobs at Bangalore startups, evaluate eligibility, tailor resumes, and track applications — powered by AI.',
  keywords: ['job discovery', 'Bangalore startups', 'resume tailoring', 'job application tracker'],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}
      </body>
    </html>
  );
}
