-- Staff-only dispatch archive (alerts, cases, medical history)
-- Run in the Supabase SQL editor after profiles.sql.

create table if not exists public.dispatch_cases (
  id uuid primary key,
  patient_id uuid,
  patient_name text,
  patient_email text,
  ambulance_id text,
  hospital_name text,
  hospital jsonb,
  pickup jsonb,
  route jsonb,
  pickup_route jsonb,
  eta_minutes double precision,
  pickup_minutes double precision,
  transport_minutes double precision,
  phase text default 'pickup',
  medical jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

create table if not exists public.dispatch_alerts (
  id uuid primary key,
  role text not null check (role in ('driver', 'staff')),
  ambulance_id text,
  title text,
  body text,
  mission_id uuid,
  payload jsonb default '{}'::jsonb,
  read boolean default false,
  created_at timestamptz default now()
);

create table if not exists public.medical_events (
  id bigint generated always as identity primary key,
  user_id uuid,
  patient_email text,
  cardiac boolean default false,
  diabetes boolean default false,
  epilepsy boolean default false,
  pregnant boolean default false,
  notes text,
  created_at timestamptz default now()
);

alter table public.dispatch_cases enable row level security;
alter table public.dispatch_alerts enable row level security;
alter table public.medical_events enable row level security;

drop policy if exists "dispatch_cases_staff_select" on public.dispatch_cases;
create policy "dispatch_cases_staff_select"
  on public.dispatch_cases for select
  using (exists (select 1 from public.profiles p where p.id = auth.uid() and p.role in ('staff', 'main_admin')));

drop policy if exists "medical_events_staff_select" on public.medical_events;
create policy "medical_events_staff_select"
  on public.medical_events for select
  using (exists (select 1 from public.profiles p where p.id = auth.uid() and p.role in ('staff', 'main_admin')));

drop policy if exists "dispatch_alerts_staff_or_driver" on public.dispatch_alerts;
create policy "dispatch_alerts_staff_or_driver"
  on public.dispatch_alerts for select
  using (
    exists (select 1 from public.profiles p where p.id = auth.uid() and p.role in ('staff', 'main_admin'))
    or (
      role = 'driver'
      and exists (select 1 from public.profiles p where p.id = auth.uid() and p.role = 'driver')
    )
  );

create index if not exists dispatch_cases_created_at_idx on public.dispatch_cases (created_at desc);
create index if not exists dispatch_alerts_role_idx on public.dispatch_alerts (role, created_at desc);
create index if not exists medical_events_user_idx on public.medical_events (user_id, created_at desc);

create table if not exists public.patient_health_profiles (
  id uuid primary key references public.profiles (id) on delete cascade,
  user_id uuid,
  allergies text default '',
  medicines text default '',
  conditions text default '',
  cardiac boolean default false,
  diabetes boolean default false,
  epilepsy boolean default false,
  pregnant boolean default false,
  visits jsonb default '[]'::jsonb,
  doctors jsonb default '[]'::jsonb,
  notes text default '',
  updated_at timestamptz default now()
);

create table if not exists public.patient_chat_messages (
  id uuid primary key,
  user_id uuid,
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  created_at timestamptz default now()
);

create table if not exists public.trip_reports (
  id uuid primary key,
  mission_id uuid,
  patient_id uuid,
  patient_name text,
  patient_email text,
  hospital_name text,
  ambulance_id text,
  body text not null,
  created_at timestamptz default now()
);

alter table public.patient_health_profiles enable row level security;
alter table public.patient_chat_messages enable row level security;
alter table public.trip_reports enable row level security;

create index if not exists patient_chat_user_idx on public.patient_chat_messages (user_id, created_at);
create index if not exists trip_reports_patient_idx on public.trip_reports (patient_id, created_at desc);

drop policy if exists "patient_chat_own_select" on public.patient_chat_messages;
create policy "patient_chat_own_select"
  on public.patient_chat_messages for select
  using (user_id = auth.uid());

drop policy if exists "patient_chat_own_insert" on public.patient_chat_messages;
create policy "patient_chat_own_insert"
  on public.patient_chat_messages for insert
  with check (user_id = auth.uid());

drop policy if exists "patient_health_own_select" on public.patient_health_profiles;
create policy "patient_health_own_select"
  on public.patient_health_profiles for select
  using (id = auth.uid() or user_id = auth.uid());

drop policy if exists "trip_reports_own_select" on public.trip_reports;
create policy "trip_reports_own_select"
  on public.trip_reports for select
  using (patient_id = auth.uid());

create table if not exists public.tavus_conversations (
  conversation_id text primary key,
  user_id uuid not null,
  created_at timestamptz default now()
);

alter table public.tavus_conversations enable row level security;

drop policy if exists "tavus_conversations_own_select" on public.tavus_conversations;
create policy "tavus_conversations_own_select"
  on public.tavus_conversations for select
  using (user_id = auth.uid());

create index if not exists tavus_conversations_user_idx on public.tavus_conversations (user_id, created_at desc);
