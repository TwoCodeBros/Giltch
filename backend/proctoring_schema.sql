-- Proctoring Module Schema Extension
-- Add this to your existing schema

-- 1. Proctoring Configuration Table
create table if not exists public.proctoring_config (
  id uuid default uuid_generate_v4() primary key,
  contest_id uuid references public.contests(id) on delete cascade unique,
  enabled boolean default true,
  max_violations integer default 10,
  auto_disqualify boolean default true,
  warning_threshold integer default 5,
  grace_violations integer default 2,
  strict_mode boolean default false,
  
  -- Monitoring Settings
  track_tab_switches boolean default true,
  track_focus_loss boolean default true,
  block_copy boolean default true,
  block_paste boolean default true,
  block_cut boolean default true,
  block_selection boolean default false,
  block_right_click boolean default true,
  detect_screenshot boolean default true,
  
  -- Violation Penalties
  tab_switch_penalty integer default 1,
  copy_paste_penalty integer default 2,
  screenshot_penalty integer default 3,
  focus_loss_penalty integer default 1,
  
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

-- 2. Enhanced Violations Table (extends existing)
-- If violations table exists, we'll add columns via ALTER
-- Otherwise create it with enhanced fields

create table if not exists public.violations (
  id uuid default uuid_generate_v4() primary key,
  participant_id uuid references public.participants(id) on delete cascade,
  contest_id uuid references public.contests(id) on delete cascade,
  round_id uuid references public.rounds(id) on delete set null,
  
  violation_type text not null, -- 'tab_switch', 'copy', 'paste', 'screenshot', 'focus_loss', 'right_click', 'restricted_key'
  severity text check (severity in ('low', 'medium', 'high', 'critical')) default 'medium',
  penalty_points integer default 1,
  
  -- Context
  question_id uuid references public.questions(id) on delete set null,
  current_round text,
  
  -- Details
  details jsonb default '{}'::jsonb, -- Store additional context like key pressed, duration, etc.
  
  -- Admin Actions
  manually_added boolean default false,
  admin_notes text,
  
  timestamp timestamp with time zone default now()
);

-- 3. Participant Proctoring Status
create table if not exists public.participant_proctoring (
  id uuid default uuid_generate_v4() primary key,
  participant_id uuid references public.participants(id) on delete cascade unique,
  contest_id uuid references public.contests(id) on delete cascade,
  
  total_violations integer default 0,
  violation_score integer default 0, -- Weighted score based on severity
  risk_level text check (risk_level in ('low', 'medium', 'high', 'critical')) default 'low',
  
  is_disqualified boolean default false,
  disqualified_at timestamp with time zone,
  disqualification_reason text,
  
  is_suspended boolean default false,
  suspended_at timestamp with time zone,
  suspension_reason text,
  
  -- Activity Tracking
  tab_switches integer default 0,
  focus_losses integer default 0,
  copy_attempts integer default 0,
  paste_attempts integer default 0,
  screenshot_attempts integer default 0,
  
  last_violation_at timestamp with time zone,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

-- 4. Proctoring Logs (Audit Trail)
create table if not exists public.proctoring_logs (
  id uuid default uuid_generate_v4() primary key,
  contest_id uuid references public.contests(id) on delete cascade,
  participant_id uuid references public.participants(id) on delete cascade,
  
  action_type text not null, -- 'violation_detected', 'warning_sent', 'disqualified', 'suspended', 'reinstated', 'violation_reset'
  action_by text, -- 'system' or admin user_id
  
  details jsonb default '{}'::jsonb,
  timestamp timestamp with time zone default now()
);

-- 5. Proctoring Alerts
create table if not exists public.proctoring_alerts (
  id uuid default uuid_generate_v4() primary key,
  contest_id uuid references public.contests(id) on delete cascade,
  participant_id uuid references public.participants(id) on delete cascade,
  
  alert_type text not null, -- 'high_violations', 'repeated_violations', 'suspicious_pattern', 'threshold_reached'
  severity text check (severity in ('info', 'warning', 'critical')) default 'warning',
  message text not null,
  
  is_read boolean default false,
  read_at timestamp with time zone,
  
  created_at timestamp with time zone default now()
);

-- Indexes for performance
create index if not exists idx_violations_participant on public.violations(participant_id);
create index if not exists idx_violations_contest on public.violations(contest_id);
create index if not exists idx_violations_timestamp on public.violations(timestamp desc);
create index if not exists idx_participant_proctoring_contest on public.participant_proctoring(contest_id);
create index if not exists idx_proctoring_logs_contest on public.proctoring_logs(contest_id);
create index if not exists idx_proctoring_alerts_contest on public.proctoring_alerts(contest_id, is_read);

-- Triggers for auto-updating timestamps
create or replace function update_updated_at_column()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger update_proctoring_config_updated_at before update on public.proctoring_config
  for each row execute procedure update_updated_at_column();

create trigger update_participant_proctoring_updated_at before update on public.participant_proctoring
  for each row execute procedure update_updated_at_column();
