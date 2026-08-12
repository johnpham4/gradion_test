'use client';

import { useEffect, useState } from 'react';
import { api, Project, ApiError } from '../lib/api';

interface ProjectListProps {
  onSelectProject: (project: Project) => void;
  onNewProject: () => void;
  onSignOut: () => void;
  currentUser: any;
}

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

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'CREATED':
        return 'bg-gray-100 text-gray-800';
      case 'STYLE_SET':
        return 'bg-blue-100 text-blue-800';
      case 'CHARACTERS_GENERATED':
        return 'bg-green-100 text-green-800';
      case 'PORTRAITS_GENERATED':
        return 'bg-purple-100 text-purple-800';
      case 'CHAPTERS_GENERATED':
        return 'bg-yellow-100 text-yellow-800';
      case 'DONE':
        return 'bg-emerald-100 text-emerald-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-orange-50 to-amber-100 p-4">
      <div className="max-w-4xl mx-auto">
        <div className="bg-white rounded-2xl shadow-xl p-8">
          <div className="flex justify-between items-center mb-8">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">
                Book Illustration Studio
              </h1>
              <p className="text-gray-600">Welcome, {currentUser?.name}</p>
            </div>
            <button
              onClick={onSignOut}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 transition"
            >
              Sign Out
            </button>
          </div>

          <div className="mb-6">
            <button
              onClick={onNewProject}
              className="w-full bg-orange-600 text-white py-3 px-4 rounded-lg hover:bg-orange-700 focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 transition"
            >
              + New Project
            </button>
          </div>

          {loading && (
            <div className="text-center py-8">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-orange-600"></div>
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
            <div className="text-center py-12">
              <div className="text-gray-400 mb-4">
                <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">No projects yet</h3>
              <p className="text-gray-600">Create your first project to get started</p>
            </div>
          )}

          {!loading && !error && projects.length > 0 && (
            <div className="space-y-4">
              {projects.map((project) => (
                <div
                  key={project.id}
                  onClick={() => onSelectProject(project)}
                  className="border border-gray-200 rounded-lg p-6 hover:border-orange-300 hover:shadow-md cursor-pointer transition"
                >
                  <div className="flex justify-between items-start mb-3">
                    <h3 className="text-lg font-semibold text-gray-900">{project.title}</h3>
                    <span className={'px-3 py-1 rounded-full text-xs font-medium ' + getStatusColor(project.overall_status)}>
                      {project.overall_status.replace('_', ' ')}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600">
                    Created: {new Date(project.created_at).toLocaleDateString()}
                  </p>
                  <div className="mt-3">
                    <div className="flex items-center">
                      <div className="flex-1 bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-orange-600 h-2 rounded-full transition-all"
                          style={{ width: ((project.current_step / 5) * 100) + '%' }}
                        ></div>
                      </div>
                      <span className="ml-3 text-sm text-gray-600">Step {project.current_step}/5</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
