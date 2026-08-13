'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
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

const STEPS = [
  { key: 'STYLE', label: 'Style' },
  { key: 'CHARACTERS', label: 'Characters' },
  { key: 'PORTRAITS', label: 'Portraits' },
  { key: 'CHAPTERS', label: 'Chapters' },
  { key: 'ILLUSTRATIONS', label: 'Illustrations' },
];

const CAPTIONS: Record<string, string> = {
  STYLE: 'Reading your book text and defining an art style',
  CHARACTERS: 'Generating the character list from your book’s text',
  PORTRAITS: 'Generating character portraits',
  CHAPTERS: 'Generating a chapter illustration prompt',
  ILLUSTRATIONS: 'Generating the chapter illustration',
};

export default function ProjectDetail({ project, onBack }: ProjectDetailProps) {
  const [bookText, setBookText] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [projectData, setProjectData] = useState<Project>(project);
  const [triggeringStep, setTriggeringStep] = useState<string | null>(null);
  const [userStyle, setUserStyle] = useState<string>('');
  const [polling, setPolling] = useState(false);
  const [bookModalOpen, setBookModalOpen] = useState(false);
  const closeBtnRef = useRef<HTMLButtonElement>(null);

  const loadBookText = useCallback(async () => {
    try {
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

  // Close the book modal on Escape, restore focus on close
  useEffect(() => {
    if (!bookModalOpen) return;
    closeBtnRef.current?.focus();
    const onKeydown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setBookModalOpen(false);
    };
    document.addEventListener('keydown', onKeydown);
    return () => document.removeEventListener('keydown', onKeydown);
  }, [bookModalOpen]);

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

  const currentIdx = Math.min(projectData.current_step, STEPS.length);
  const currentStep = currentIdx < STEPS.length ? STEPS[currentIdx] : null;
  const currentStatus = currentStep ? getStepStatus(currentStep.key) : null;
  const running = currentStep && currentStatus === 'RUNNING';
  const stranded = currentStep && currentStatus === 'STRANDED';
  const failed = currentStep && currentStatus === 'FAILED';
  const style = getStyle();
  const characters = getCharacters();
  const portraits = getPortraits();
  const chapters = getChapters();
  const illustrations = getIllustrations();

  const bookTextTruncated = bookText.replace(/\s+/g, ' ').trim().length > 220;
  const bookSnippet =
    bookText.replace(/\s+/g, ' ').trim().length > 220
      ? bookText.replace(/\s+/g, ' ').trim().slice(0, 220) + '…'
      : bookText;

  const buildMainPanel = () => {
    if (!currentStep) {
      return (
        <div className="step-panel">
          <div className="status-line" style={{ color: 'var(--grad-ink)' }}>
            <span className="gd-num-square done" style={{ width: 20, height: 20, fontSize: 11 }}>✓</span>
            All 5 steps complete — nothing left to generate.
          </div>
          <p className="help">This project is done. Reopen it any time; nothing here regenerates automatically.</p>
        </div>
      );
    }

    if (stranded) {
      const stepState = projectData.step_states?.[currentStep.key];
      return (
        <div className="step-panel">
          <div className="status-line" style={{ color: 'var(--grad-ink)' }}>
            This step was interrupted (probably a page refresh or server restart mid-request) and never finished.
          </div>
          {stepState?.error_message && <p className="err-text">{stepState.error_message}</p>}
          <p className="help">Nothing before this step was affected — everything already generated is saved. Retrying is safe.</p>
          <button
            className="gd-btn gd-btn-warn"
            style={{ marginTop: 14 }}
            disabled={triggeringStep === currentStep.key}
            onClick={() => retryStep(currentStep.key)}
          >
            {triggeringStep === currentStep.key ? 'Recovering…' : 'Recover ' + currentStep.label}
          </button>
        </div>
      );
    }

    if (failed) {
      const stepState = projectData.step_states?.[currentStep.key];
      return (
        <div className="step-panel">
          <div className="status-line" style={{ color: 'var(--grad-ink)' }}>
            This step failed. Retry it to continue the pipeline.
          </div>
          {stepState?.error_message && <p className="err-text">{stepState.error_message}</p>}
          <button
            className="gd-btn gd-btn-danger"
            style={{ marginTop: 14 }}
            disabled={triggeringStep === currentStep.key}
            onClick={() => retryStep(currentStep.key)}
          >
            {triggeringStep === currentStep.key ? 'Retrying…' : 'Retry ' + currentStep.label}
          </button>
        </div>
      );
    }

    const isStyleStep = currentStep.key === 'STYLE';
    return (
      <div className="step-panel">
        {running ? (
          <div className="status-line">
            <span className="spinner sm"></span> {CAPTIONS[currentStep.key]} — usually a couple of seconds with the mock provider, longer for real Gemini calls…
          </div>
        ) : (
          <div className="status-line" style={{ color: 'var(--grad-ink)' }}>
            Ready for the next step: <b>&nbsp;{currentStep.label}</b>.
          </div>
        )}
        {isStyleStep && !running && (
          <div className="gd-field" style={{ marginBottom: 14 }}>
            <label htmlFor="style-input">Art style (optional)</label>
            <input
              id="style-input"
              value={userStyle}
              onChange={(e) => setUserStyle(e.target.value)}
              placeholder="Leave blank to let Gemini choose a style based on your book"
              disabled={triggeringStep === currentStep.key}
            />
          </div>
        )}
        <p className="help">Reopening this page mid-step won&apos;t fire a second request — it just shows the same in-flight state until it lands.</p>
        <button
          className="gd-btn gd-btn-primary"
          style={{ marginTop: 14 }}
          disabled={!!running || triggeringStep === currentStep.key}
          onClick={() => triggerStep(currentStep.key)}
        >
          {running ? 'Generating…' : 'Generate ' + currentStep.label}
          {!running && <span className="gd-arrow">→</span>}
        </button>
      </div>
    );
  };

  const entityCardHtml = (
    item: NamedResult,
    kind: 'portrait' | 'illustration',
    imagePath: string | null | undefined,
    generating: boolean
  ) => {
    const artClass = kind === 'illustration' ? 'art chapter' : 'art';
    let art;
    if (imagePath) {
      art = (
        <div className={artClass}>
          {/* Images come from the backend with a session cookie; next/image
              would bypass the cookie, so a plain img is required here. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={api.imageUrl(imagePath) || undefined}
            alt={kind === 'portrait' ? `Portrait of ${item.name}` : `Illustration of ${item.name}`}
          />
        </div>
      );
    } else if (generating) {
      art = (
        <div className={artClass + ' pending'}>
          <div style={{ textAlign: 'center' }}>
            <span className="spinner sm"></span>
            <div className="gen-caption">
              Generating {kind === 'portrait' ? 'portrait for ' + item.name : 'illustration'}…
            </div>
          </div>
        </div>
      );
    } else {
      art = (
        <div className={artClass + ' pending'}>
          <span className="placeholder-label muted">Not generated yet</span>
        </div>
      );
    }
    return (
      <div className="entity-card">
        {art}
        <div className="body">
          <h5>{item.name}</h5>
          <p>{item.prompt}</p>
        </div>
      </div>
    );
  };

  const portraitsRunning = running && currentStep?.key === 'PORTRAITS';
  const illustrationsRunning = running && currentStep?.key === 'ILLUSTRATIONS';

  const sideNote =
    style !== '' ? (
      <div className="side-note">
        <h5>Style</h5>
        <p>{style}</p>
      </div>
    ) : (
      <div className="side-note">
        <h5>Book text</h5>
        <p style={{ fontStyle: 'italic' }}>{bookSnippet}</p>
        {bookTextTruncated && (
          <button
            type="button"
            className="gd-btn gd-btn-ghost gd-btn-sm"
            style={{ paddingLeft: 0, marginTop: 8 }}
            onClick={() => setBookModalOpen(true)}
          >
            Read full text →
          </button>
        )}
      </div>
    );

  return (
    <div>
      <div className="app-body">
        <a className="back-link" onClick={onBack}>← Back to projects</a>
        <h2 style={{ fontSize: 22, marginBottom: 4 }}>{projectData.title}</h2>
        <p className="meta" style={{ marginBottom: 24 }}>
          Created {new Date(projectData.created_at).toLocaleDateString()}
        </p>

        <div className="stepper">
          {STEPS.map((s, i) => {
            const done = i < currentIdx;
            const isCurrent = i === currentIdx;
            const cls = done ? 'done' : isCurrent ? 'current' : 'pending';
            const sq = done
              ? <span className="gd-num-square done">✓</span>
              : <span className={'gd-num-square ' + (isCurrent ? '' : 'gray')}>{i + 1}</span>;
            return (
              <div key={s.key} style={{ display: 'contents' }}>
                <div className={'step ' + cls}>
                  {sq}
                  <span className="lbl">{s.label}</span>
                </div>
                {i < STEPS.length - 1 && (
                  <div className={'connector ' + (i < currentIdx ? 'done' : '')}></div>
                )}
              </div>
            );
          })}
        </div>

        <div className="detail-grid">
          <div>
            {buildMainPanel()}
            <div style={{ marginTop: 28 }}>
              {(() => {
                const sections: Array<{ title: string; single: boolean; body: React.ReactNode }> = [];
                if (illustrations.length) {
                  sections.push({
                    title: `Illustrations (${illustrations.length})`,
                    single: true,
                    body: illustrations.map((it, i) => (
                      <div key={i}>{entityCardHtml(it, 'illustration', it.illustration_path, !!illustrationsRunning)}</div>
                    )),
                  });
                }
                if (portraits.length) {
                  sections.push({
                    title: `Portraits (${portraits.length})`,
                    single: false,
                    body: portraits.map((it, i) => (
                      <div key={i}>{entityCardHtml(it, 'portrait', it.portrait_path, !!portraitsRunning)}</div>
                    )),
                  });
                }
                if (chapters.length) {
                  sections.push({
                    title: `Chapters (${chapters.length})`,
                    single: true,
                    body: chapters.map((c, i) => (
                      <div key={i} className="entity-card">
                        <div className="body">
                          <h5>{c.name}</h5>
                          <p>{c.prompt}</p>
                        </div>
                      </div>
                    )),
                  });
                }
                if (characters.length) {
                  sections.push({
                    title: `Characters (${characters.length})`,
                    single: false,
                    body: characters.map((c, i) => (
                      <div key={i} className="entity-card">
                        <div className="body">
                          <h5>{c.name}</h5>
                          <p>{c.prompt}</p>
                        </div>
                      </div>
                    )),
                  });
                }
                return sections.map((sec) => (
                  <div key={sec.title} style={{ marginBottom: 28 }}>
                    <div className="panel-title"><h3>{sec.title}</h3></div>
                    <div className="entity-grid" style={{ gridTemplateColumns: sec.single ? '1fr' : 'repeat(2, 1fr)' }}>
                      {sec.body}
                    </div>
                  </div>
                ));
              })()}
            </div>

            {error && (
              <div style={{ marginTop: 20, padding: 12, border: '1px solid #f0c0c0', borderRadius: 8, background: '#fff5f5' }}>
                <p className="err-text" style={{ margin: 0 }}>{error}</p>
              </div>
            )}
          </div>

          <div>{sideNote}</div>
        </div>
      </div>

      {bookModalOpen && (
        <div className="modal-overlay" onClick={(e) => { if (e.target === e.currentTarget) setBookModalOpen(false); }}>
          <div className="modal-box" role="dialog" aria-modal="true" aria-labelledby="book-modal-title">
            <div className="modal-head">
              <h4 id="book-modal-title" style={{ margin: 0 }}>Full book text</h4>
              <button
                type="button"
                className="modal-close"
                ref={closeBtnRef}
                onClick={() => setBookModalOpen(false)}
                aria-label="Close"
              >
                ✕
              </button>
            </div>
            <div className="modal-body">{bookText}</div>
          </div>
        </div>
      )}
    </div>
  );
}