'use client';

import { useState } from 'react';
import { api, CreateProjectRequest, ApiError, Project } from '../lib/api';

interface NewProjectProps {
  onCancel: () => void;
  onProjectCreated: (project: Project) => void;
}

export default function NewProject({ onCancel, onProjectCreated }: NewProjectProps) {
  const [title, setTitle] = useState('');
  const [bookText, setBookText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [useFileUpload, setUseFileUpload] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (!title.trim()) {
        setError('Project title is required');
        setLoading(false);
        return;
      }

      if (!useFileUpload && !bookText.trim()) {
        setError('Book text is required');
        setLoading(false);
        return;
      }

      if (!useFileUpload && bookText.trim().length < 10) {
        setError('Book text must be at least 10 characters');
        setLoading(false);
        return;
      }

      if (useFileUpload && !file) {
        setError('Please select a file');
        setLoading(false);
        return;
      }

      if (useFileUpload && file && !file.name.endsWith('.txt')) {
        setError('Only .txt files are supported');
        setLoading(false);
        return;
      }

      const request: CreateProjectRequest = {
        title: title.trim(),
        book_text: useFileUpload ? undefined : bookText.trim(),
        file: useFileUpload ? file || undefined : undefined,
      };

      const response = await api.createProject(request);
      onProjectCreated(response);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to create project. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      if (!selectedFile.name.endsWith('.txt')) {
        setError('Only .txt files are supported');
        setFile(null);
        return;
      }
      setFile(selectedFile);
      setError(null);
    }
  };

  return (
    <div className="app-body narrow">
      <a className="back-link" onClick={onCancel}>← Back to projects</a>
      <h3 style={{ fontSize: 20 }}>Start a new illustration project</h3>
      <p className="meta" style={{ marginBottom: 20 }}>
        Give it a title, then paste the book&apos;s text or upload a .txt file.
      </p>

      <form onSubmit={handleSubmit} className="gd-field">
        <div className="gd-field">
          <label htmlFor="title">Project title <span className="req">*</span></label>
          <input
            type="text"
            id="title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. The Wind in the Willows — cottage-core"
            disabled={loading}
          />
        </div>

        <div className="gd-field" style={{ marginTop: 16 }}>
          <label>Book text <span className="req">*</span></label>
          <div
            className={'dropzone ' + (file && useFileUpload ? 'has-file' : '')}
            onClick={() => document.getElementById('file-input')?.click()}
          >
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--grad-ink)' }}>
              {file && useFileUpload ? '✓ ' + file.name + ' loaded' : 'Click to choose a .txt file'}
            </div>
            <div className="hint">Plain text only · used once as context for every step below</div>
          </div>
          <input
            type="file"
            id="file-input"
            accept=".txt"
            style={{ display: 'none' }}
            onChange={(e) => {
              setUseFileUpload(true);
              handleFileChange(e);
            }}
            disabled={loading}
          />

          <div className="divider-or">or paste text</div>
          <div className="gd-field">
            <textarea
              id="bookText"
              rows={5}
              value={bookText}
              onChange={(e) => {
                setBookText(e.target.value);
                setUseFileUpload(false);
              }}
              placeholder="Once upon a time, in a small burrow by the river..."
              disabled={loading}
            />
            <p className="meta" style={{ marginTop: 4 }}>
              {bookText.length}/10 minimum characters
            </p>
          </div>
        </div>

        {error && <div className="err-text">{error}</div>}

        <button
          type="submit"
          disabled={loading}
          className="gd-btn gd-btn-primary"
          style={{ width: '100%', justifyContent: 'center', marginTop: 20 }}
        >
          {loading ? 'Creating…' : 'Create project'} {!loading && <span className="gd-arrow">→</span>}
        </button>

        <button
          type="button"
          onClick={onCancel}
          disabled={loading}
          className="gd-btn gd-btn-secondary"
          style={{ width: '100%', justifyContent: 'center', marginTop: 12 }}
        >
          Cancel
        </button>
      </form>
    </div>
  );
}