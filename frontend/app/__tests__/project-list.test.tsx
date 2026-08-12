import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ProjectList from '../components/ProjectList';
import { api } from '../lib/api';

// Mock the API
jest.mock('../lib/api');

describe('ProjectList Component', () => {
  const mockUser = { email: 'test@example.com', name: 'Test User', projects: [] };
  const mockOnSelectProject = jest.fn();
  const mockOnNewProject = jest.fn();
  const mockOnSignOut = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders loading state initially', () => {
    (api.getProjects as jest.Mock).mockImplementation(() => new Promise(() => {}));

    render(
      <ProjectList
        onSelectProject={mockOnSelectProject}
        onNewProject={mockOnNewProject}
        onSignOut={mockOnSignOut}
        currentUser={mockUser}
      />
    );

    expect(screen.getByText('Loading projects...')).toBeInTheDocument();
  });

  it('renders empty state when no projects', async () => {
    (api.getProjects as jest.Mock).mockResolvedValue({ projects: [] });

    render(
      <ProjectList
        onSelectProject={mockOnSelectProject}
        onNewProject={mockOnNewProject}
        onSignOut={mockOnSignOut}
        currentUser={mockUser}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('No projects yet')).toBeInTheDocument();
    });
  });

  it('renders project list', async () => {
    const mockProjects = [
      {
        id: '1',
        title: 'Test Project',
        created_at: '2024-08-12T00:00:00Z',
        overall_status: 'CREATED',
        current_step: 0,
        user_email: 'test@example.com',
        characters: [],
        chapters: []
      }
    ];
    (api.getProjects as jest.Mock).mockResolvedValue({ projects: mockProjects });

    render(
      <ProjectList
        onSelectProject={mockOnSelectProject}
        onNewProject={mockOnNewProject}
        onSignOut={mockOnSignOut}
        currentUser={mockUser}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument();
    });
  });

  it('calls onNewProject when button is clicked', async () => {
    (api.getProjects as jest.Mock).mockResolvedValue({ projects: [] });

    render(
      <ProjectList
        onSelectProject={mockOnSelectProject}
        onNewProject={mockOnNewProject}
        onSignOut={mockOnSignOut}
        currentUser={mockUser}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('+ New Project')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('+ New Project'));
    expect(mockOnNewProject).toHaveBeenCalled();
  });

  it('calls onSignOut when sign out button is clicked', async () => {
    (api.getProjects as jest.Mock).mockResolvedValue({ projects: [] });

    render(
      <ProjectList
        onSelectProject={mockOnSelectProject}
        onNewProject={mockOnNewProject}
        onSignOut={mockOnSignOut}
        currentUser={mockUser}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Sign Out')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Sign Out'));
    expect(mockOnSignOut).toHaveBeenCalled();
  });
});
