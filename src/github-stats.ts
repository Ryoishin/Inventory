import { useCallback, useEffect, useState } from 'react';
import { config } from './config';

export type Repo = {
  id: string;
  name: string;
  full_name: string;
  description: string | null;
  language: string | null;
  stargazers_count: number;
  updated_at: string;
  html_url: string;
  homepage: string | null;
  fork: boolean;
  topics: string[];
};

export type GitHubProfile = {
  public_repos: number;
  followers: number;
  following: number;
};

export type GitHubLanguage = {
  name: string;
  bytes: number;
  percentage: number;
};

export type GitHubStats = {
  total_contributions: number;
  current_streak: number;
  longest_streak: number;
  public_repositories: number;
  total_stars: number;
  followers: number;
  total_commits: number;
};

export type GitHubDashboard = {
  profile: GitHubProfile;
  stats: GitHubStats;
  languages: GitHubLanguage[];
  repos: Repo[];
  updated_at: string;
  stale: boolean;
};

export type GitHubDashboardState = 'loading' | 'ready' | 'error';

export function useGitHubDashboard() {
  const [dashboard, setDashboard] = useState<GitHubDashboard | null>(null);
  const [state, setState] = useState<GitHubDashboardState>('loading');
  const [requestNumber, setRequestNumber] = useState(0);
  const retry = useCallback(() => setRequestNumber((number) => number + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    const apiBase = config.apiUrl.replace(/\/$/, '');

    async function loadDashboard() {
      setState('loading');
      try {
        const response = await fetch(`${apiBase}/api/github/stats`, {
          headers: { Accept: 'application/json' },
          signal: controller.signal,
        });
        if (!response.ok) throw new Error('GitHub statistics unavailable');
        const data = (await response.json()) as GitHubDashboard;
        if (!data.profile || !data.stats || !Array.isArray(data.repos) || !Array.isArray(data.languages)) {
          throw new Error('Invalid GitHub statistics response');
        }
        setDashboard(data);
        setState('ready');
      } catch {
        if (!controller.signal.aborted) {
          setDashboard(null);
          setState('error');
        }
      }
    }

    void loadDashboard();
    return () => controller.abort();
  }, [requestNumber]);

  return { dashboard, state, retry };
}
