-- Sentinel Dispatch: initial persistence (dispatch history)
-- Run this in Supabase SQL Editor.

create table if not exists public.dispatches (
  id bigint generated always as identity primary key,
  -- local_id: in-app dispatch id (so the backend can update/cancel/ack reliably)
  local_id int,
  -- user_id: Supabase Auth user id (UUID) who triggered the dispatch (optional)
  user_id uuid,
  trauma_type text,
  trauma_level int,
  incident_lat double precision,
  incident_lng double precision,
  ambulance_id text,
  hospital_id text,
  hospital_name text,
  eta_seconds int,
  distance_km double precision,
  golden_alert boolean default false,
  arrival_acknowledged boolean default false,
  cancelled boolean default false,
  created_at timestamptz default now()
);

-- If the table already existed, ensure new columns exist (safe to re-run).
alter table public.dispatches add column if not exists local_id int;
alter table public.dispatches add column if not exists user_id uuid;

-- Helpful index for "recent dispatches" queries
create index if not exists dispatches_created_at_idx on public.dispatches (created_at desc);

-- Helpful indexes for app lookups
create unique index if not exists dispatches_local_id_uidx on public.dispatches (local_id);
create index if not exists dispatches_user_id_idx on public.dispatches (user_id);
