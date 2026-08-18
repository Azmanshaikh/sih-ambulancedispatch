-- AI medical-report analyses stored per signed-in account.
-- Run in the Supabase SQL editor (service role writes from the FastAPI backend).

create table if not exists public.medical_reports (
  id uuid primary key,
  user_id uuid,
  email text,
  input_text text,
  analysis text not null,
  image_name text,
  created_at timestamptz default now()
);

alter table public.medical_reports enable row level security;

drop policy if exists "medical_reports_own_select" on public.medical_reports;
create policy "medical_reports_own_select"
  on public.medical_reports for select
  using (
    user_id = auth.uid()
    or exists (select 1 from public.profiles p where p.id = auth.uid() and p.role = 'staff')
  );

create index if not exists medical_reports_user_idx on public.medical_reports (user_id, created_at desc);
