import { supabase } from '$lib/supabase';
import type { Session } from '@supabase/supabase-js';

export type Role = 'patient' | 'driver' | 'staff';

export type Profile = {
  id: string;
  email: string;
  full_name?: string;
  role: Role;
  status: string;
  requested_role?: string | null;
  ambulance_id?: string | null;
  onboarded?: boolean;
  needs_onboarding?: boolean;
};

export const auth = $state({
  session: null as Session | null,
  profile: null as Profile | null,
  ready: false,
});

export function needsOnboarding(profile?: Profile | null) {
  const p = profile || auth.profile;
  if (!p) return false;
  if (p.needs_onboarding) return true;
  if (p.status === 'pending') return true;
  if (p.onboarded === false && p.role === 'patient') return true;
  return false;
}

export function homeFor(role?: string | null) {
  if (needsOnboarding()) return '/choose-role';
  const r = role || auth.profile?.role;
  if (r === 'staff') return '/';
  if (r === 'driver') return '/driver';
  return '/patient';
}

export async function authHeaders(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function backendOrigin() {
  const raw = String(import.meta.env.VITE_BACKEND_URL || '')
    .trim()
    .replace(/\/$/, '');
  if (raw) return raw;
  return import.meta.env.DEV ? 'http://localhost:8000' : '';
}

export async function apiFetch(path: string, init: RequestInit = {}) {
  const backendUrl = backendOrigin();
  const headers: Record<string, string> = {
    ...((init.headers as Record<string, string>) || {}),
    ...(await authHeaders()),
  };
  return fetch(`${backendUrl}${path}`, { ...init, headers });
}

export async function refreshProfile() {
  if (!auth.session) {
    auth.profile = null;
    return null;
  }
  const res = await apiFetch('/accounts/me');
  if (!res.ok) return null;
  const data = await res.json();
  auth.profile = data.user as Profile;
  return auth.profile;
}

export async function initAuth() {
  const { data } = await supabase.auth.getSession();
  auth.session = data.session;
  if (auth.session) await refreshProfile();
  auth.ready = true;
  supabase.auth.onAuthStateChange(async (_event, next) => {
    auth.session = next;
    if (next) await refreshProfile();
    else auth.profile = null;
  });
}

export async function signInWithGoogle() {
  const redirectTo = `${window.location.origin}/auth/callback`;
  const { error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: { redirectTo },
  });
  if (error) throw error;
}

export async function signOut() {
  await supabase.auth.signOut();
  auth.session = null;
  auth.profile = null;
}
