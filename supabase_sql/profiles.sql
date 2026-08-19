-- JEEVAN: Gmail auth profiles + staff-gated role requests
-- Copy this entire file into the Supabase SQL editor and run it.
-- Safe to re-run on an existing project.

create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text,
  full_name text,
  role text not null default 'patient' check (role in ('patient', 'driver', 'staff', 'doctor')),
  status text not null default 'active' check (status in ('active', 'pending')),
  requested_role text check (requested_role is null or requested_role in ('driver', 'staff', 'doctor')),
  ambulance_id text,
  hospital_id integer,
  updated_at timestamptz default now()
);

-- Existing projects created the table before hospital_id / doctor existed.
alter table public.profiles add column if not exists hospital_id integer;

alter table public.profiles drop constraint if exists profiles_role_check;
alter table public.profiles add constraint profiles_role_check
  check (role in ('patient', 'driver', 'staff', 'doctor'));
alter table public.profiles drop constraint if exists profiles_requested_role_check;
alter table public.profiles add constraint profiles_requested_role_check
  check (requested_role is null or requested_role in ('driver', 'staff', 'doctor'));
alter table public.role_requests drop constraint if exists role_requests_requested_role_check;
alter table public.role_requests add constraint role_requests_requested_role_check
  check (requested_role in ('driver', 'staff', 'doctor'));

create table if not exists public.role_requests (
  id bigint generated always as identity primary key,
  user_id uuid not null references public.profiles (id) on delete cascade,
  requested_role text not null check (requested_role in ('driver', 'staff', 'doctor')),
  status text not null default 'pending' check (status in ('pending', 'approved', 'denied')),
  reviewed_by uuid references public.profiles (id),
  created_at timestamptz default now(),
  reviewed_at timestamptz
);

alter table public.profiles enable row level security;
alter table public.role_requests enable row level security;

drop policy if exists "profiles_select_own_or_staff" on public.profiles;
create policy "profiles_select_own_or_staff"
  on public.profiles for select
  using (
    auth.uid() = id
    or exists (select 1 from public.profiles p where p.id = auth.uid() and p.role = 'staff')
  );

drop policy if exists "profiles_update_own" on public.profiles;
create policy "profiles_update_own"
  on public.profiles for update
  using (auth.uid() = id)
  with check (auth.uid() = id);

drop policy if exists "profiles_insert_own" on public.profiles;
create policy "profiles_insert_own"
  on public.profiles for insert
  with check (auth.uid() = id);

drop policy if exists "role_requests_select" on public.role_requests;
create policy "role_requests_select"
  on public.role_requests for select
  using (
    auth.uid() = user_id
    or exists (select 1 from public.profiles p where p.id = auth.uid() and p.role = 'staff')
  );

drop policy if exists "role_requests_insert_own" on public.role_requests;
create policy "role_requests_insert_own"
  on public.role_requests for insert
  with check (auth.uid() = user_id);

create index if not exists role_requests_status_idx on public.role_requests (status);
create index if not exists profiles_role_idx on public.profiles (role);
create index if not exists profiles_hospital_id_idx on public.profiles (hospital_id);
