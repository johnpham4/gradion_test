'use client';

import { useState, useEffect } from 'react';
import { api, Project, ApiError } from '../lib/api';

interface ProjectDetailProps {
  project: Project;
  onBack: () => void;
}

export default function ProjectDetail({ project, onBack }: ProjectDetailProps) {
  const [bookText, setBookText] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (project.book_text) {
      setBookText(project.book_text);
      setLoading(false);
    } else {
      loadBookText();
    }
  }, [project]);

  const loadBookText = async () => {
    try {
      setLoading(true);
      setError(null);
      const fullProject = await api.getProject(project.id);
      setBookText(fullProject.book_text || '');
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to load book text');
      }
    } finally {
      setLoading(false);
    }
  };

  const getStepStatus = (step: number) => {
    if (project.current_step > step) return 'completed';
    if (project.current_step === step) return 'current';
    return 'pending';
  };

  const steps = [
    { name: 'Style', description: 'Define art style' },
    { name: 'Characters', description: 'Extract characters' },
    { name: 'Portraits', description: 'Generate portraits' },
    { name: 'Chapters', description: 'Create chapter prompts' },
    { name: 'Illustrations', description: 'Generate illustrations' },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-orange-50 to-amber-100 p-4">
      <div className="max-w-4xl mx-auto">
        <div className="bg-white rounded-2xl shadow-xl p-8">
          <div className="mb-6">
            <button
              onClick={onBack}
              className="text-sm text-gray-600 hover:text-gray-800 transition mb-4 inline-block"
            >
              ← Back to Projects
            </button>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">{project.title}</h1>
            <p className="text-gray-600">
              Created: {new Date(project.created_at).toLocaleString()}
            </p>
          </div>

          {/* Pipeline Steps */}
          <div className="mb-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Pipeline Progress</h2>
            <div className="space-y-3">
              {steps.map((step, index) => {
                const status = getStepStatus(index);
                return (
                  <div
                    key={index}
                    className={'flex items-center p-4 rounded-lg border ' + (
                      status === 'completed'
                        ? 'border-green-200 bg-green-50'
                        : status === 'current'
                        ? 'border-orange-200 bg-orange-50'
                        : 'border-gray-200 bg-gray-50'
                    )}
                  >
                    <div
                      className={'w-8 h-8 rounded-full flex items-center justify-center mr-4 ' + (
                        status === 'completed'
                          ? 'bg-green-600 text-white'
                          : status === 'current'
                          ? 'bg-orange-600 text-white'
                          : 'bg-gray-300 text-gray-600'
                      )}
                    >
                      {status === 'completed' ? '✓' : index + 1}
                    </div>
                    <div className="flex-1">
                      <h3 className="font-medium text-gray-900">{step.name}</h3>
                      <p className="text-sm text-gray-600">{step.description}</p>
                    </div>
                    {status === 'current' && (
                      <span className="text-sm text-orange-600 font-medium">In Progress</span>
                    )}
                    {status === 'completed' && (
                      <span className="text-sm text-green-600 font-medium">Completed</span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Book Text */}
          <div>
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Book Text</h2>
            {loading ? (
              <div className="text-center py-8">
                <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-orange-600"></div>
                <p className="mt-2 text-gray-600">Loading book text...</p>
              </div>
            ) : error ? (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <p className="text-sm text-red-600">{error}</p>
                <button
                  onClick={loadBookText}
                  className="mt-2 text-sm text-red-600 hover:text-red-800 underline"
                >
                  Retry
                </button>
              </div>
            ) : (
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-6">
                <pre className="whitespace-pre-wrap text-sm text-gray-800 font-sans max-h-96 overflow-y-auto">
                  {bookText}
                </pre>
              </div>
            )}
          </div>

          <div className="mt-8 pt-6 border-t border-gray-200">
            <p className="text-xs text-gray-500 text-center">
              Pipeline execution controls will be available in Phase 3
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
