'use client';

import { useState } from 'react';
import { api, CreateProjectRequest, ApiError } from '../lib/api';

interface NewProjectProps {
  onCancel: () => void;
  onProjectCreated: (project: any) => void;
}

export default function NewProject({ onCancel, onProjectCreated }: NewProjectProps) {
  const [title, setTitle] = useState('');
  const [bookText, setBookText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [useFileUpload, setUseFileUpload] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (!title.trim()) {
        setError('Project title is required');
        setLoading(false);
        return;
      }

      if (!useFileUpload && !bookText.trim()) {
        setError('Book text is required');
        setLoading(false);
        return;
      }

      if (!useFileUpload && bookText.trim().length < 10) {
        setError('Book text must be at least 10 characters');
        setLoading(false);
        return;
      }

      if (useFileUpload && !file) {
        setError('Please select a file');
        setLoading(false);
        return;
      }

      if (useFileUpload && file && !file.name.endsWith('.txt')) {
        setError('Only .txt files are supported');
        setLoading(false);
        return;
      }

      const request: CreateProjectRequest = {
        title: title.trim(),
        book_text: useFileUpload ? undefined : bookText.trim(),
        file: useFileUpload ? file : undefined,
      };

      const response = await api.createProject(request);
      onProjectCreated(response);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to create project. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      setError(null);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-orange-50 to-amber-100 flex items-center justify-center p-4">
      <div className="max-w-2xl w-full">
        <div className="bg-white rounded-2xl shadow-xl p-8">
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              Create New Project
            </h1>
            <p className="text-gray-600">Upload your book text to get started</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="title" className="block text-sm font-medium text-gray-700 mb-2">
                Project Title
              </label>
              <input
                type="text"
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none transition"
                placeholder="Enter project title"
                disabled={loading}
              />
            </div>

            <div>
              <div className="flex space-x-4 mb-4">
                <button
                  type="button"
                  onClick={() => setUseFileUpload(false)}
                  className={'flex-1 py-2 px-4 rounded-lg transition ' + (
                    !useFileUpload
                      ? 'bg-orange-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  )}
                  disabled={loading}
                >
                  Paste Text
                </button>
                <button
                  type="button"
                  onClick={() => setUseFileUpload(true)}
                  className={'flex-1 py-2 px-4 rounded-lg transition ' + (
                    useFileUpload
                      ? 'bg-orange-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  )}
                  disabled={loading}
                >
                  Upload File
                </button>
              </div>

              {!useFileUpload ? (
                <div>
                  <label htmlFor="bookText" className="block text-sm font-medium text-gray-700 mb-2">
                    Book Text
                  </label>
                  <textarea
                    id="bookText"
                    value={bookText}
                    onChange={(e) => setBookText(e.target.value)}
                    rows={10}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none transition resize-none"
                    placeholder="Paste your book text here..."
                    disabled={loading}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    {bookText.length}/10 minimum characters
                  </p>
                </div>
              ) : (
                <div>
                  <label htmlFor="file" className="block text-sm font-medium text-gray-700 mb-2">
                    Upload .txt File
                  </label>
                  <input
                    type="file"
                    id="file"
                    accept=".txt"
                    onChange={handleFileChange}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none transition"
                    disabled={loading}
                  />
                  {file && (
                    <p className="text-sm text-gray-600 mt-2">
                      Selected: {file.name}
                    </p>
                  )}
                </div>
              )}
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <p className="text-sm text-red-600">{error}</p>
              </div>
            )}

            <div className="flex space-x-4">
              <button
                type="button"
                onClick={onCancel}
                disabled={loading}
                className="flex-1 bg-gray-100 text-gray-700 py-3 px-4 rounded-lg hover:bg-gray-200 focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="flex-1 bg-orange-600 text-white py-3 px-4 rounded-lg hover:bg-orange-700 focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition"
              >
                {loading ? 'Creating...' : 'Create Project'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
