'use client';

import { useState, useEffect } from 'react';
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

  useEffect(() => {
    setView('signin');
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
