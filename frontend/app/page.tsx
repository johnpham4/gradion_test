'use client';

import { useState, useEffect } from 'react';
import SignIn from './components/SignIn';
import ProjectList from './components/ProjectList';
import NewProject from './components/NewProject';
import ProjectDetail from './components/ProjectDetail';
import { api, ApiError } from './lib/api';

type View = 'signin' | 'projects' | 'new-project' | 'project-detail';

export default function Home() {
  const [view, setView] = useState<View>('signin');
  const [currentUser, setCurrentUser] = useState<any>(null);
  const [selectedProject, setSelectedProject] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check if user is already authenticated by trying to fetch projects
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      setLoading(true);
      await api.getProjects();
      // If successful, user is authenticated, but we need user info
      // For now, we'll stay on signin since we don't have a get current user endpoint
      setView('signin');
    } catch (err) {
      // Not authenticated, stay on signin
      setView('signin');
    } finally {
      setLoading(false);
    }
  };

  const handleSignIn = (user: any) => {
    setCurrentUser(user);
    setView('projects');
  };

  const handleSignOut = async () => {
    try {
      await api.signOut();
      setCurrentUser(null);
      setSelectedProject(null);
      setView('signin');
    } catch (err) {
      console.error('Sign out error:', err);
    }
  };

  const handleSelectProject = (project: any) => {
    setSelectedProject(project);
    setView('project-detail');
  };

  const handleNewProject = () => {
    setView('new-project');
  };

  const handleProjectCreated = (project: any) => {
    setSelectedProject(project);
    setView('project-detail');
  };

  const handleBackToProjects = () => {
    setSelectedProject(null);
    setView('projects');
  };

  const handleCancelNewProject = () => {
    setView('projects');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-orange-50 to-amber-100 flex items-center justify-center p-4">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-orange-600"></div>
          <p className="mt-2 text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  if (view === 'signin') {
    return <SignIn onSignIn={handleSignIn} />;
  }

  if (view === 'projects') {
    return (
      <ProjectList
        onSelectProject={handleSelectProject}
        onNewProject={handleNewProject}
        onSignOut={handleSignOut}
        currentUser={currentUser}
      />
    );
  }

  if (view === 'new-project') {
    return (
      <NewProject
        onCancel={handleCancelNewProject}
        onProjectCreated={handleProjectCreated}
      />
    );
  }

  if (view === 'project-detail' && selectedProject) {
    return (
      <ProjectDetail
        project={selectedProject}
        onBack={handleBackToProjects}
      />
    );
  }

  return null;
}
