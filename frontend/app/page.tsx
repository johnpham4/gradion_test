'use client';

import { useState, useEffect, useCallback } from 'react';
import SignIn from './components/SignIn';
import ProjectList from './components/ProjectList';
import NewProject from './components/NewProject';
import ProjectDetail from './components/ProjectDetail';
import { api, Project } from './lib/api';

type View = 'signin' | 'projects' | 'new-project' | 'project-detail';

export default function Home() {
  const [view, setView] = useState<View>('signin');
  const [currentUser, setCurrentUser] = useState<{ email: string; name: string } | null>(null);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);

  const checkAuth = useCallback(async () => {
    try {
      setLoading(true);
      await api.getProjects();
      // If successful, user is authenticated
      // We'll use the user info from sign-in response stored in session
      // For now, just set view to projects
      setView('projects');
    } catch {
      // Not authenticated, stay on signin
      setView('signin');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Skip auth check for now - always start on signin page
    setView('signin');
    setLoading(false);
  }, []);

  const handleSignIn = (user: { email: string; name: string }) => {
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

  const handleSelectProject = (project: Project) => {
    setSelectedProject(project);
    setView('project-detail');
  };

  const handleNewProject = () => {
    setView('new-project');
  };

  const handleProjectCreated = (project: Project) => {
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
