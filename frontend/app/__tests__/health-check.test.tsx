import { render, screen, waitFor } from '@testing-library/react';
import Home from '../page';

// Mock fetch globally
global.fetch = jest.fn();

describe('Health Check Page', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('shows loading state initially', () => {
    (global.fetch as jest.Mock).mockImplementation(() => new Promise(() => {}));
    render(<Home />);
    
    expect(screen.getByText('Connecting to backend...')).toBeInTheDocument();
  });

  it('displays health status when backend is reachable', async () => {
    const mockHealth = {
      status: 'healthy',
      timestamp: '2024-08-12T17:00:00Z',
      version: '1.0.0'
    };

    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => mockHealth
    });

    render(<Home />);

    await waitFor(() => {
      expect(screen.getByText('Backend Connected')).toBeInTheDocument();
    });

    expect(screen.getByText('Status: healthy')).toBeInTheDocument();
    expect(screen.getByText('Version: 1.0.0')).toBeInTheDocument();
  });

  it('displays error when backend is unreachable', async () => {
    (global.fetch as jest.Mock).mockRejectedValue(new Error('Network error'));

    render(<Home />);

    await waitFor(() => {
      expect(screen.getByText('Connection Error')).toBeInTheDocument();
    });

    expect(screen.getByText('Failed to connect to backend')).toBeInTheDocument();
  });

  it('retries connection when retry button is clicked', async () => {
    (global.fetch as jest.Mock)
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: 'healthy',
          timestamp: '2024-08-12T17:00:00Z',
          version: '1.0.0'
        })
      });

    render(<Home />);

    await waitFor(() => {
      expect(screen.getByText('Connection Error')).toBeInTheDocument();
    });

    const retryButton = screen.getByText('Retry Connection');
    retryButton.click();

    await waitFor(() => {
      expect(screen.getByText('Backend Connected')).toBeInTheDocument();
    });
  });
});