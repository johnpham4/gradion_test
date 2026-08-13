'use client';

import { useState, useEffect, useCallback } from 'react';
import { api, Project, ApiError } from '../lib/api';

interface ProjectDetailProps {
  project: Project;
  onBack: () => void;
}

interface NamedResult {
  name: string;
  prompt: string;
}

interface PortraitResult extends NamedResult {
  portrait_path?: string | null;
}

interface IllustrationResult extends NamedResult {
  illustration_path?: string | null;
}

export default function ProjectDetail({ project, onBack }: ProjectDetailProps) {
  const [bookText, setBookText] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [projectData, setProjectData] = useState<Project>(project);
  const [triggeringStep, setTriggeringStep] = useState<string | null>(null);
  const [userStyle, setUserStyle] = useState<string>('');
  const [polling, setPolling] = useState(false);

  const loadBookText = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const fullProject = await api.getProject(project.id);
      setBookText(fullProject.book_text || '');
      setProjectData(fullProject);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to load book text');
      }
    } finally {
      setLoading(false);
    }
  }, [project.id]);

  const loadProjectData = useCallback(async () => {
    try {
      const updated = await api.getProject(project.id);
      setProjectData(updated);
    } catch (err) {
      console.error('Failed to load project data:', err);
    }
  }, [project.id]);

  useEffect(() => {
    if (project.book_text) {
      setBookText(project.book_text);
      setLoading(false);
    } else {
      loadBookText();
    }
    loadProjectData();
  }, [project, loadBookText, loadProjectData]);

  // Poll for project updates when a step is running
  useEffect(() => {
    if (polling) {
      const interval = setInterval(async () => {
        try {
          const updated = await api.getProject(project.id);
          setProjectData(updated);

          // Check if any step is still running
          const hasRunningStep = Object.values(updated.step_states || {}).some(
            (state: { status: string }) => state.status === 'RUNNING'
          );

          if (!hasRunningStep) {
            setPolling(false);
          }
        } catch (err) {
          console.error('Polling error:', err);
          setPolling(false);
        }
      }, 2000); // Poll every 2 seconds

      return () => clearInterval(interval);
    }
  }, [polling, project.id]);

  const triggerStep = async (step: string) => {
    try {
      setTriggeringStep(step);
      setError(null);
      // Start polling BEFORE the trigger call so the RUNNING state and any
      // partial results (persisted by the backend) show up during long steps.
      setPolling(true);

      // For STYLE step, pass user style if provided
      if (step === 'STYLE' && userStyle.trim()) {
        await api.triggerStep(project.id, step, userStyle.trim());
      } else {
        await api.triggerStep(project.id, step);
      }

      // Refresh immediately so results render without waiting for the next poll
      await loadProjectData();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to trigger step');
      }
      setPolling(false);
    } finally {
      setTriggeringStep(null);
    }
  };

  const retryStep = async (step: string) => {
    try {
      setTriggeringStep(step);
      setError(null);
      setPolling(true);
      await api.retryStep(project.id, step);
      await loadProjectData();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to retry step');
      }
      setPolling(false);
    } finally {
      setTriggeringStep(null);
    }
  };

  const getStepStatus = (stepName: string) => {
    const stepStates = projectData.step_states || {};
    const stepState = stepStates[stepName];
    if (!stepState) return 'PENDING';
    return stepState.status;
  };

  const getStepResult = (stepName: string): Record<string, unknown> | undefined => {
    return projectData.step_states?.[stepName]?.result;
  };

  const getStyle = (): string => {
    const result = getStepResult('STYLE');
    return typeof result?.style === 'string' ? result.style : '';
  };

  const getCharacters = (): NamedResult[] => {
    const result = getStepResult('CHARACTERS');
    return Array.isArray(result?.characters) ? (result.characters as NamedResult[]) : [];
  };

  const getPortraits = (): PortraitResult[] => {
    const result = getStepResult('PORTRAITS');
    return Array.isArray(result?.portraits) ? (result.portraits as PortraitResult[]) : [];
  };

  const getChapters = (): NamedResult[] => {
    const result = getStepResult('CHAPTERS');
    return Array.isArray(result?.chapters) ? (result.chapters as NamedResult[]) : [];
  };

  const getIllustrations = (): IllustrationResult[] => {
    const result = getStepResult('ILLUSTRATIONS');
    return Array.isArray(result?.illustrations) ? (result.illustrations as IllustrationResult[]) : [];
  };

  const canTriggerStep = (stepIndex: number) => {
    // Can trigger if current_step matches index and step is not completed
    return projectData.current_step === stepIndex;
  };

  const steps = [
    { name: 'STYLE', label: 'Style', description: 'Define art style' },
    { name: 'CHARACTERS', label: 'Characters', description: 'Extract characters' },
    { name: 'PORTRAITS', label: 'Portraits', description: 'Generate portraits' },
    { name: 'CHAPTERS', label: 'Chapters', description: 'Create chapter prompts' },
    { name: 'ILLUSTRATIONS', label: 'Illustrations', description: 'Generate illustrations' },
  ];

  return (
    <div className='min-h-screen bg-gradient-to-br from-orange-50 to-amber-100 p-4'>
      <div className='max-w-6xl mx-auto'>
        <div className='bg-white rounded-2xl shadow-xl p-8'>
          <div className='mb-6'>
            <button
              onClick={onBack}
              className='text-sm text-gray-600 hover:text-gray-800 transition mb-4 inline-block'
            >
              ← Back to Projects
            </button>
            <h1 className='text-3xl font-bold text-gray-900 mb-2'>{projectData.title}</h1>
            <p className='text-gray-600'>
              Created: {new Date(projectData.created_at).toLocaleString()}
            </p>
          </div>

          {/* Pipeline Steps */}
          <div className='mb-8'>
            <h2 className='text-xl font-semibold text-gray-900 mb-4'>Pipeline Progress</h2>
            <div className='space-y-3'>
              {steps.map((step, index) => {
                const status = getStepStatus(step.name);
                const canTrigger = canTriggerStep(index);
                const stepState = projectData.step_states?.[step.name];
                const errorMessage = stepState?.error_message;
                const style = getStyle();
                const characters = getCharacters();
                const portraits = getPortraits();
                const chapters = getChapters();
                const illustrations = getIllustrations();

                return (
                  <div key={index}>
                    <div
                      className={'flex items-center p-4 rounded-lg border ' + (
                        status === 'COMPLETED'
                          ? 'border-green-200 bg-green-50'
                          : status === 'RUNNING'
                          ? 'border-orange-200 bg-orange-50'
                          : status === 'FAILED'
                          ? 'border-red-200 bg-red-50'
                          : status === 'STRANDED'
                          ? 'border-yellow-200 bg-yellow-50'
                          : 'border-gray-200 bg-gray-50'
                      )}
                    >
                      <div
                        className={'w-8 h-8 rounded-full flex items-center justify-center mr-4 ' + (
                          status === 'COMPLETED'
                            ? 'bg-green-600 text-white'
                            : status === 'RUNNING'
                            ? 'bg-orange-600 text-white'
                            : status === 'FAILED'
                            ? 'bg-red-600 text-white'
                            : status === 'STRANDED'
                            ? 'bg-yellow-600 text-white'
                            : 'bg-gray-300 text-gray-600'
                        )}
                      >
                        {status === 'COMPLETED' ? '✓' : index + 1}
                      </div>
                      <div className='flex-1'>
                        <h3 className='font-medium text-gray-900'>{step.label}</h3>
                        <p className='text-sm text-gray-600'>{step.description}</p>
                        {errorMessage && (status === 'FAILED' || status === 'STRANDED') && (
                          <p className='text-sm text-red-600 mt-1'>{errorMessage}</p>
                        )}
                      </div>
                      <div className='flex items-center space-x-2'>
                        {status === 'RUNNING' && (
                          <span className='text-sm text-orange-600 font-medium'>Running...</span>
                        )}
                        {status === 'COMPLETED' && (
                          <span className='text-sm text-green-600 font-medium'>Completed</span>
                        )}
                        {status === 'FAILED' && (
                          <button
                            onClick={() => retryStep(step.name)}
                            disabled={triggeringStep === step.name}
                            className='text-sm bg-red-600 text-white px-3 py-1 rounded hover:bg-red-700 disabled:opacity-50'
                          >
                            {triggeringStep === step.name ? 'Retrying...' : 'Retry'}
                          </button>
                        )}
                        {status === 'STRANDED' && (
                          <button
                            onClick={() => retryStep(step.name)}
                            disabled={triggeringStep === step.name}
                            className='text-sm bg-yellow-600 text-white px-3 py-1 rounded hover:bg-yellow-700 disabled:opacity-50'
                          >
                            {triggeringStep === step.name ? 'Recovering...' : 'Recover'}
                          </button>
                        )}
                        {canTrigger && status === 'PENDING' && (
                          <button
                            onClick={() => triggerStep(step.name)}
                            disabled={triggeringStep === step.name}
                            className='text-sm bg-orange-600 text-white px-3 py-1 rounded hover:bg-orange-700 disabled:opacity-50'
                          >
                            {triggeringStep === step.name ? 'Starting...' : 'Start'}
                          </button>
                        )}
                      </div>
                    </div>

                    {/* STYLE Step - User Input */}
                    {step.name === 'STYLE' && status === 'PENDING' && canTrigger && (
                      <div className='mt-3 p-4 bg-orange-50 border border-orange-200 rounded-lg'>
                        <h3 className='font-medium text-gray-900 mb-2'>Optional: Specify Art Style</h3>
                        <p className='text-sm text-gray-600 mb-3'>
                          Leave empty to let Gemini generate a style based on your book text
                        </p>
                        <input
                          type='text'
                          value={userStyle}
                          onChange={(e) => setUserStyle(e.target.value)}
                          placeholder='e.g., watercolor, comic book, minimal flat design'
                          className='w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none'
                        />
                      </div>
                    )}

                    {/* STYLE Step - Generated style */}
                    {step.name === 'STYLE' && style && (
                      <div className='mt-3 p-4 bg-blue-50 border border-blue-200 rounded-lg'>
                        <h3 className='font-medium text-gray-900 mb-2'>Art Style</h3>
                        <p className='text-sm text-gray-700'>{style}</p>
                      </div>
                    )}

                    {/* CHARACTERS Step - Character cards */}
                    {step.name === 'CHARACTERS' && characters.length > 0 && (
                      <div className='mt-3 grid grid-cols-1 md:grid-cols-2 gap-4'>
                        {characters.map((char, idx) => (
                          <div key={idx} className='p-4 bg-gray-50 border border-gray-200 rounded-lg'>
                            <h4 className='font-medium text-gray-900'>{char.name}</h4>
                            <p className='text-sm text-gray-600 mt-1'>{char.prompt}</p>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* PORTRAITS Step - Portrait cards with images */}
                    {step.name === 'PORTRAITS' && portraits.length > 0 && (
                      <div className='mt-3 grid grid-cols-1 md:grid-cols-2 gap-4'>
                        {portraits.map((portrait, idx) => {
                          const imageUrl = api.imageUrl(portrait.portrait_path);
                          return (
                            <div key={idx} className='p-4 bg-gray-50 border border-gray-200 rounded-lg'>
                              <h4 className='font-medium text-gray-900'>{portrait.name}</h4>
                              <p className='text-sm text-gray-600 mt-1'>{portrait.prompt}</p>
                              {imageUrl ? (
                                <div className='mt-3'>
                                  {/* Images come from the backend with a session cookie; next/image
                                      would bypass the cookie, so a plain img is required here. */}
                                  {/* eslint-disable-next-line @next/next/no-img-element */}
                                  <img
                                    src={imageUrl}
                                    alt={`Portrait of ${portrait.name}`}
                                    className='w-full rounded-lg border border-gray-200'
                                  />
                                </div>
                              ) : (
                                status === 'RUNNING' && (
                                  <p className='text-sm text-orange-600 mt-2'>Generating portrait...</p>
                                )
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}

                    {/* CHAPTERS Step - Chapter cards */}
                    {step.name === 'CHAPTERS' && chapters.length > 0 && (
                      <div className='mt-3 grid grid-cols-1 gap-4'>
                        {chapters.map((chapter, idx) => (
                          <div key={idx} className='p-4 bg-gray-50 border border-gray-200 rounded-lg'>
                            <h4 className='font-medium text-gray-900'>{chapter.name}</h4>
                            <p className='text-sm text-gray-600 mt-1'>{chapter.prompt}</p>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* ILLUSTRATIONS Step - Illustration cards with images */}
                    {step.name === 'ILLUSTRATIONS' && illustrations.length > 0 && (
                      <div className='mt-3 grid grid-cols-1 gap-4'>
                        {illustrations.map((illustration, idx) => {
                          const imageUrl = api.imageUrl(illustration.illustration_path);
                          return (
                            <div key={idx} className='p-4 bg-gray-50 border border-gray-200 rounded-lg'>
                              <h4 className='font-medium text-gray-900'>{illustration.name}</h4>
                              <p className='text-sm text-gray-600 mt-1'>{illustration.prompt}</p>
                              {imageUrl ? (
                                <div className='mt-3'>
                                  {/* Images come from the backend with a session cookie; next/image
                                      would bypass the cookie, so a plain img is required here. */}
                                  {/* eslint-disable-next-line @next/next/no-img-element */}
                                  <img
                                    src={imageUrl}
                                    alt={`Illustration of ${illustration.name}`}
                                    className='w-full rounded-lg border border-gray-200'
                                  />
                                </div>
                              ) : (
                                status === 'RUNNING' && (
                                  <p className='text-sm text-orange-600 mt-2'>Generating illustration...</p>
                                )
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Book Text */}
          <div>
            <h2 className='text-xl font-semibold text-gray-900 mb-4'>Book Text</h2>
            {loading ? (
              <div className='text-center py-8'>
                <div className='inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-orange-600'></div>
                <p className='mt-2 text-gray-600'>Loading book text...</p>
              </div>
            ) : error ? (
              <div className='bg-red-50 border border-red-200 rounded-lg p-4'>
                <p className='text-sm text-red-600'>{error}</p>
                <button
                  onClick={loadBookText}
                  className='mt-2 text-sm text-red-600 hover:text-red-800 underline'
                >
                  Retry
                </button>
              </div>
            ) : (
              <div className='bg-gray-50 border border-gray-200 rounded-lg p-6'>
                <pre className='whitespace-pre-wrap text-sm text-gray-800 font-sans max-h-96 overflow-y-auto'>
                  {bookText}
                </pre>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
