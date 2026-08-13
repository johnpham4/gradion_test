'use client';

import { useEffect, useState } from 'react';
import { api, Project, ApiError } from '../lib/api';

interface ProjectListProps {
  onSelectProject: (project: Project) => void;
  onNewProject: () => void;
  onSignOut: () => void;
  currentUser: { email: string; name: string } | null;
}

const STEPS = ['Style', 'Characters', 'Portraits', 'Chapters', 'Illustrations'];

export default function ProjectList({ onSelectProject, onNewProject, onSignOut, currentUser }: ProjectListProps) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.getProjects();
      setProjects(response.projects);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to load projects');
      }
    } finally {
      setLoading(false);
    }
  };

  const getPillClass = (status: string) => {
    if (status === 'CREATED') return 'gd-pill gray';
    if (status === 'DONE') return 'gd-pill ink';
    return 'gd-pill';
  };

  const getStatusLabel = (status: string) => {
    if (status === 'CREATED') return 'Draft';
    if (status === 'DONE') return 'Done';
    return 'In progress';
  };

  const getSubtitle = (project: Project) => {
    if (project.overall_status === 'CREATED') return 'Book text saved · style not yet generated';
    if (project.overall_status === 'DONE') return 'All 5 steps complete';
    const done = Math.min(project.current_step, STEPS.length);
    return STEPS.slice(0, done).join(' + ') + ' done';
  };

  const getProgressSegments = (currentStep: number) => {
    const segments = [];
    for (let i = 0; i < 5; i++) {
      segments.push(i < currentStep);
    }
    return segments;
  };

  const initials = (currentUser?.name || '?')
    .split(' ')
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  return (
    <div>
      <nav className="gd-nav">
        <div className="gd-nav-inner">
          <div className="gd-nav-logo" onClick={onNewProject}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/gradion-logo.png" alt="Gradion" className="gd-nav-logo-img" />
          </div>
          <div className="gd-nav-links">
            <a onClick={onNewProject}>Projects</a>
          </div>
          <div className="gd-nav-user">
            <div className="gd-nav-avatar">{initials}</div>
            {currentUser?.name}
            <a onClick={onSignOut}>Sign Out</a>
          </div>
        </div>
      </nav>

      <div className="app-body">
        <div className="list-head">
          <h2>Your projects</h2>
          <button className="gd-btn gd-btn-primary" onClick={onNewProject}>+ New Project</button>
        </div>

        {loading && (
          <div className="text-center py-8">
            <div className="inline-block spinner"></div>
            <p className="mt-2 text-gray-600">Loading projects...</p>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <p className="text-sm text-red-600">{error}</p>
            <button
              onClick={loadProjects}
              className="mt-2 text-sm text-red-600 hover:text-red-800 underline"
            >
              Retry
            </button>
          </div>
        )}

        {!loading && !error && projects.length === 0 && (
          <div className="empty-state">
            <p style={{ margin: 0 }}>No projects yet</p>
            <button className="gd-btn gd-btn-primary" onClick={onNewProject}>+ New Project</button>
          </div>
        )}

        {!loading && !error && projects.length > 0 && (
          <div className="project-list">
            {projects.map((project, i) => (
              <div
                key={project.id}
                onClick={() => onSelectProject(project)}
                className="project-row"
                style={{ ['--stagger' as string]: `${i * 45}ms` }}
              >
                <div className="title">
                  <h4>{project.title}</h4>
                  <span className="meta">
                    Created {new Date(project.created_at).toLocaleDateString()} · {getSubtitle(project)}
                  </span>
                </div>
                <div className="progress-mini">
                  {getProgressSegments(project.current_step).map((active, idx) => (
                    <span key={idx} className={'seg ' + (active ? 'on' : '')}></span>
                  ))}
                </div>
                <span className={getPillClass(project.overall_status)}>
                  {project.overall_status !== 'CREATED' && project.overall_status !== 'DONE' && (
                    <span className="dot"></span>
                  )}
                  {getStatusLabel(project.overall_status)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}