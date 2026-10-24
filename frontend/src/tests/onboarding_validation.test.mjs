import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

// Validation logic mirroring frontend ReviewStep
function validateProfileForm(fields) {
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
}

function normalizeSkills(skillsString) {
  if (!skillsString) return [];
  return Array.from(
    new Set(
      skillsString
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)
    )
  );
}

function validateUploadFile(file) {
  const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024;
  if (!file) return 'Please select a file to upload.';
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    return 'Only PDF files are accepted for resume upload.';
  }
  if (file.size === 0) {
    return 'The selected file is empty. Please upload a valid PDF resume.';
  }
  if (file.size > MAX_FILE_SIZE_BYTES) {
    return 'File exceeds maximum size of 50 MB.';
  }
  return null;
}

describe('Frontend Upload Validation', () => {
  test('accepts valid PDF under 50 MB', () => {
    const file = { name: 'resume.pdf', size: 1024 * 500 };
    assert.equal(validateUploadFile(file), null);
  });

  test('rejects non-PDF extension', () => {
    const file = { name: 'resume.docx', size: 1024 };
    assert.match(validateUploadFile(file), /Only PDF files are accepted/);
  });

  test('rejects 0-byte empty file', () => {
    const file = { name: 'empty.pdf', size: 0 };
    assert.match(validateUploadFile(file), /empty/i);
  });

  test('rejects file larger than 50 MB', () => {
    const file = { name: 'huge.pdf', size: 51 * 1024 * 1024 };
    assert.match(validateUploadFile(file), /exceeds maximum size of 50 MB/);
  });
});

describe('Frontend Profile Form Validation', () => {
  test('passes for valid candidate details', () => {
    const fields = {
      full_name: 'John Doe',
      email: 'john@example.com',
      phone: '+919876543210',
      location: 'Bangalore',
      degree: 'B.Tech',
      graduation_year: '2024',
      cgpa: '8.5',
      cgpa_scale: '10.0',
      skills: 'Python, React, TypeScript',
    };
    assert.equal(validateProfileForm(fields), null);
  });

  test('rejects malformed email', () => {
    const fields = {
      email: 'invalid-email',
      graduation_year: '',
      cgpa: '',
      cgpa_scale: '',
    };
    assert.match(validateProfileForm(fields), /valid email address/);
  });

  test('rejects out-of-range graduation year', () => {
    assert.match(
      validateProfileForm({ email: '', graduation_year: '1965', cgpa: '', cgpa_scale: '' }),
      /between 1970 and 2035/
    );
    assert.match(
      validateProfileForm({ email: '', graduation_year: '2045', cgpa: '', cgpa_scale: '' }),
      /between 1970 and 2035/
    );
  });

  test('rejects negative CGPA', () => {
    assert.match(
      validateProfileForm({ email: '', graduation_year: '', cgpa: '-1.0', cgpa_scale: '10.0' }),
      /non-negative number/
    );
  });

  test('rejects zero or negative CGPA scale', () => {
    assert.match(
      validateProfileForm({ email: '', graduation_year: '', cgpa: '8.0', cgpa_scale: '0' }),
      /positive number/
    );
  });

  test('rejects CGPA greater than CGPA scale', () => {
    assert.match(
      validateProfileForm({ email: '', graduation_year: '', cgpa: '9.5', cgpa_scale: '4.0' }),
      /cannot exceed the stated scale/
    );
  });

  test('requires scale if CGPA is provided', () => {
    assert.match(
      validateProfileForm({ email: '', graduation_year: '', cgpa: '8.5', cgpa_scale: '' }),
      /specify the CGPA scale/
    );
  });

  test('normalizes and deduplicates skills', () => {
    const skills = normalizeSkills('  Python , python, React, REACT  , TypeScript  , ');
    // Case-preserving deduplication
    assert.deepEqual(skills, ['Python', 'python', 'React', 'REACT', 'TypeScript']);
  });
});
