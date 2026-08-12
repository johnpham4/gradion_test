import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import SignIn from '../components/SignIn';
import { api } from '../lib/api';

// Mock the API
jest.mock('../lib/api');

describe('SignIn Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders sign-in form', () => {
    const mockOnSignIn = jest.fn();
    render(<SignIn onSignIn={mockOnSignIn} />);

    expect(screen.getByLabelText('Name')).toBeInTheDocument();
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
    expect(screen.getByText('Sign In')).toBeInTheDocument();
  });

  it('shows validation error for empty fields', async () => {
    const mockOnSignIn = jest.fn();
    render(<SignIn onSignIn={mockOnSignIn} />);

    const submitButton = screen.getByText('Sign In');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Name and email are required')).toBeInTheDocument();
    });

    expect(mockOnSignIn).not.toHaveBeenCalled();
  });

  it('calls sign-in API with valid data', async () => {
    const mockUser = { email: 'test@example.com', name: 'Test User', projects: [] };
    const mockOnSignIn = jest.fn();
    (api.signIn as jest.Mock).mockResolvedValue({ user: mockUser });

    render(<SignIn onSignIn={mockOnSignIn} />);

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Test User' } });
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'test@example.com' } });

    const submitButton = screen.getByText('Sign In');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(api.signIn).toHaveBeenCalledWith({
        name: 'Test User',
        email: 'test@example.com'
      });
    });

    await waitFor(() => {
      expect(mockOnSignIn).toHaveBeenCalledWith(mockUser);
    });
  });

  it('handles API errors', async () => {
    const mockOnSignIn = jest.fn();
    (api.signIn as jest.Mock).mockRejectedValue(new Error('API Error'));

    render(<SignIn onSignIn={mockOnSignIn} />);

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Test User' } });
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'test@example.com' } });

    const submitButton = screen.getByText('Sign In');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Failed to sign in. Please try again.')).toBeInTheDocument();
    });

    expect(mockOnSignIn).not.toHaveBeenCalled();
  });
});
