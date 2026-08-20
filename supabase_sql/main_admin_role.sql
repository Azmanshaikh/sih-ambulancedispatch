-- JEEVAN: add main_admin role for route simulation access
-- Safe to re-run on an existing project.

alter table public.profiles drop constraint if exists profiles_role_check;
alter table public.profiles add constraint profiles_role_check
  check (role in ('patient', 'driver', 'staff', 'doctor', 'main_admin'));
