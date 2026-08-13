'use client';

import { useState } from 'react';
import { api, ApiError } from '../lib/api';

interface SignInProps {
  onSignIn: (user: { email: string; name: string }) => void;
}

export default function SignIn({ onSignIn }: SignInProps) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (!name.trim() || !email.trim()) {
        setError('Name and email are required');
        setLoading(false);
        return;
      }

      if (!email.includes('@')) {
        setError('Please enter a valid email address');
        setLoading(false);
        return;
      }

      const response = await api.signIn({ name: name.trim(), email: email.trim() });
      onSignIn(response.user as { email: string; name: string });
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to sign in. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="center-page">
      <div className="auth-card">
        <div className="logo-row">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/gradion-logo.png" alt="Gradion" />
        </div>
        <h3 style={{ textAlign: 'center', fontSize: 20 }}>Book Illustration Studio</h3>
        <p className="lede">Enter your details to start or resume an illustration project.</p>

        <form onSubmit={handleSubmit} className="gd-field">
          <div className="gd-field">
            <label htmlFor="name">Name</label>
            <input
              type="text"
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Mira Hassan"
              disabled={loading}
            />
          </div>
          <div className="gd-field">
            <label htmlFor="email">Email</label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="mira@example.com"
              disabled={loading}
            />
          </div>
          {error && <div className="err-text">{error}</div>}
          <button type="submit" disabled={loading} className="gd-btn gd-btn-primary">
            {loading ? 'Signing in…' : 'Sign In'} {!loading && <span className="gd-arrow">→</span>}
          </button>
        </form>

        <p className="meta">
          No password — this is a lightweight identity check. Using an email that already
          has projects resumes them exactly where you left off.
        </p>
      </div>
    </div>
  );
}