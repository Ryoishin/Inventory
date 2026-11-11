import {
  Activity,
  Flame,
  GitCommitHorizontal,
  GitFork,
  RotateCw,
  Star,
  TrendingUp,
  Users,
} from 'lucide-react';
import type { GitHubDashboard, GitHubDashboardState } from './github-stats';

type Props = {
  dashboard: GitHubDashboard | null;
  state: GitHubDashboardState;
  onRetry: () => void;
};

const numberFormat = new Intl.NumberFormat('en-US');

function formatUpdatedAt(value: string) {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? 'recently'
    : parsed.toLocaleString(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
        timeZone: 'UTC',
      }) + ' UTC';
}

export default function GitHubStatsDashboard({ dashboard, state, onRetry }: Props) {
  const cards = dashboard
    ? [
        {
          label: 'Total contributions',
          value: numberFormat.format(dashboard.stats.total_contributions),
          detail: 'all-time GitHub calendar',
          icon: Activity,
        },
        {
          label: 'Current streak',
          value: numberFormat.format(dashboard.stats.current_streak),
          detail: 'consecutive days',
          icon: Flame,
        },
        {
          label: 'Longest streak',
          value: numberFormat.format(dashboard.stats.longest_streak),
          detail: 'consecutive days',
          icon: TrendingUp,
        },
        {
          label: 'Public repositories',
          value: numberFormat.format(dashboard.stats.public_repositories),
          detail: 'owned by this profile',
          icon: GitFork,
        },
        {
          label: 'Stars earned',
          value: numberFormat.format(dashboard.stats.total_stars),
          detail: 'on original public repos',
          icon: Star,
        },
        {
          label: 'Followers',
          value: numberFormat.format(dashboard.stats.followers),
          detail: 'GitHub profile',
          icon: Users,
        },
        {
          label: 'Commits',
          value: numberFormat.format(dashboard.stats.total_commits),
          detail: 'counted by GitHub',
          icon: GitCommitHorizontal,
        },
      ]
    : [];

  return (
    <section className="section-wrap github-stats-section" id="github-stats" aria-labelledby="github-stats-title">
      <div className="section-heading">
        <span className="section-index">LIVE / GITHUB PROFILE</span>
        <h2 id="github-stats-title">
          Activity, measured.<br />
          <span>Progress in public.</span>
        </h2>
        <p className="heading-note">
          Current profile data and contribution history, fetched securely through the portfolio API.
        </p>
      </div>

      {state === 'error' ? (
        <div className="github-stats-retry">
          <p role="status">
            GitHub activity is temporarily unavailable. The dashboard will update when the service recovers.
          </p>
          <button type="button" className="button secondary" onClick={onRetry}>
            <RotateCw size={15} aria-hidden="true" />
            Retry GitHub data
          </button>
        </div>
      ) : state === 'loading' ? (
        <div className="github-stats-grid" role="status" aria-label="Loading GitHub statistics">
          {Array.from({ length: 7 }, (_, index) => (
            <div className="github-stat-card skeleton-card" key={index} aria-hidden="true">
              <span className="skeleton-line skeleton-label" />
              <span className="skeleton-line skeleton-value" />
              <span className="skeleton-line skeleton-detail" />
            </div>
          ))}
        </div>
      ) : (
        <>
          <div className="github-stats-grid">
            {cards.map(({ label, value, detail, icon: Icon }) => (
              <article className="github-stat-card" key={label}>
                <div className="github-stat-label">
                  <span>{label}</span>
                  <Icon size={16} aria-hidden="true" />
                </div>
                <strong>{value}</strong>
                <span className="github-stat-detail">{detail}</span>
              </article>
            ))}
          </div>
          <p className={dashboard?.stale ? 'github-stats-note is-stale' : 'github-stats-note'} role="status">
            {dashboard?.stale
              ? `Showing the last successful GitHub update from ${formatUpdatedAt(dashboard.updated_at)}.`
              : `Updated ${formatUpdatedAt(dashboard?.updated_at ?? '')}. Contribution totals follow GitHub attribution rules.`}
            {' '}Private contribution counts are included only when GitHub permits them.
          </p>
        </>
      )}
    </section>
  );
}
