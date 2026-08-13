const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface User {
  email: string;
  name: string;
  projects: string[];
}

export interface StepState {
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'STRANDED';
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  result?: Record<string, unknown>;
}

export interface Project {
  id: string;
  user_email: string;
  title: string;
  created_at: string;
  overall_status: string;
  current_step: number;
  book_text?: string;
  book_text_path?: string;
  step_states?: Record<string, StepState>;
  style?: string | null;
  characters: Array<{ name: string; prompt: string; portrait_path?: string }>;
  chapters: Array<{ name: string; prompt: string; illustration_path?: string }>;
}

export interface ProjectListResponse {
  projects: Project[];
}

export interface SignInRequest {
  name: string;
  email: string;
}

export interface SignInResponse {
  user: User;
}

export interface CreateProjectRequest {
  title: string;
  book_text?: string;
  file?: File;
}

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function handleResponse(response: Response) {
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new ApiError(response.status, error.detail || error.message || 'Request failed');
  }
  return response.json();
}

export const api = {
  // Auth endpoints
  async signIn(data: SignInRequest): Promise<SignInResponse> {
    const response = await fetch(API_URL + '/api/auth/sign-in', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
      credentials: 'include',
    });
    return handleResponse(response);
  },

  async signOut(): Promise<{ message: string }> {
    const response = await fetch(API_URL + '/api/auth/sign-out', {
      method: 'POST',
      credentials: 'include',
    });
    return handleResponse(response);
  },

  // Project endpoints
  async getProjects(): Promise<ProjectListResponse> {
    const response = await fetch(API_URL + '/api/projects', {
      credentials: 'include',
    });
    return handleResponse(response);
  },

  async getProject(projectId: string): Promise<Project> {
    const response = await fetch(API_URL + '/api/projects/' + projectId, {
      credentials: 'include',
    });
    return handleResponse(response);
  },

  async createProject(data: CreateProjectRequest): Promise<Project> {
    const formData = new FormData();
    formData.append('title', data.title);
    
    if (data.file) {
      formData.append('file', data.file);
    } else if (data.book_text) {
      formData.append('book_text', data.book_text);
    }

    const response = await fetch(API_URL + '/api/projects', {
      method: 'POST',
      body: formData,
      credentials: 'include',
    });
    return handleResponse(response);
  },

  // Pipeline endpoints
  async triggerStep(projectId: string, step: string, userStyle?: string): Promise<{ status: string; result: Record<string, unknown> }> {
    const url = API_URL + '/api/projects/' + projectId + '/steps/' + step + (userStyle ? '?user_style=' + encodeURIComponent(userStyle) : '');
    const response = await fetch(url, {
      method: 'POST',
      credentials: 'include',
    });
    return handleResponse(response);
  },

  async retryStep(projectId: string, step: string): Promise<{ status: string; result: Record<string, unknown> }> {
    const response = await fetch(API_URL + '/api/projects/' + projectId + '/steps/' + step + '/retry', {
      method: 'POST',
      credentials: 'include',
    });
    return handleResponse(response);
  },

  // Build a URL for an image served from the backend (paths are "data/...")
  imageUrl(path?: string | null): string | null {
    if (!path) return null;
    return API_URL + '/api/images/' + path.replace(/^data\//, '');
  },
};

export { ApiError };
