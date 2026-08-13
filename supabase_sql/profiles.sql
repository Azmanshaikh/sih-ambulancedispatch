-- JEEVAN: Gmail auth profiles + staff-gated role requests
-- Run in the Supabase SQL editor.

create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text,
  full_name text,
  role text not null default 'patient' check (role in ('patient', 'driver', 'staff')),
  status text not null default 'active' check (status in ('active', 'pending')),
  requested_role text check (requested_role is null or requested_role in ('driver', 'staff')),
  ambulance_id text,
  updated_at timestamptz default now()
);

create table if not exists public.role_requests (
  id bigint generated always as identity primary key,
  user_id uuid not null references public.profiles (id) on delete cascade,
  requested_role text not null check (requested_role in ('driver', 'staff')),
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
