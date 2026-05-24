-- Worktree reports table for Month 4: Worktree Clean-up Automation
-- Stores the latest worktree inspection report pushed by inspect_worktrees.ps1

create table if not exists vault_worktree_reports (
  id uuid primary key default gen_random_uuid(),
  report jsonb not null,
  summary jsonb not null default '{}',
  created_at timestamptz not null default now()
);

alter table vault_worktree_reports enable row level security;

-- Allow anon read, service_role write
create policy "anon can read worktree reports"
  on vault_worktree_reports for select
  to anon
  using (true);

create policy "service_role can insert worktree reports"
  on vault_worktree_reports for insert
  to service_role
  with check (true);

-- Index for latest report lookup
create index idx_worktree_reports_created_at on vault_worktree_reports (created_at desc);
