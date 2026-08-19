<script lang="ts">
  import '../app.css';
  import TopNav from '$lib/components/TopNav.svelte';
  import InstallApp from '$lib/components/InstallApp.svelte';
  import FloatingActions from '$lib/components/FloatingActions.svelte';
  import type { Snippet } from 'svelte';
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { auth, homeFor, initAuth, needsOnboarding } from '$lib/auth.svelte';
  import { initI18n } from '$lib/i18n.svelte';
  import { supabaseConfigured } from '$lib/supabase';
  import { browser } from '$app/environment';

  interface Props { children: Snippet; }
  let { children }: Props = $props();

  let gpsStatus = $state('BMSIT College, Yelahanka');

  const PUBLIC = ['/login', '/auth/callback'];
  const NO_NAV = ['/login', '/auth/callback', '/choose-role'];

  const STAFF_PATHS = ['/', '/request', '/navigation', '/hospitals', '/notifications', '/staff/approvals'];
  const PATIENT_PATHS = ['/patient', '/ai-guide', '/ai-call'];
  const DRIVER_PATHS = ['/driver', '/hospitals'];
  const DOCTOR_PATHS = ['/doctor'];

  function allowed(pathname: string, role?: string | null) {
    if (PUBLIC.includes(pathname)) return true;
    if (needsOnboarding()) return pathname === '/choose-role';
    if (role === 'staff') return STAFF_PATHS.includes(pathname) || pathname.startsWith('/staff/');
    if (role === 'driver') return DRIVER_PATHS.includes(pathname);
    if (role === 'doctor') return DOCTOR_PATHS.includes(pathname);
    return PATIENT_PATHS.includes(pathname);
  }

  onMount(async () => {
    initI18n();
    await initAuth();
    const path = page.url.pathname;
    if (!auth.session && !PUBLIC.includes(path)) {
      goto('/login', { replaceState: true });
      return;
    }
    if (auth.session && path === '/login') {
      goto(homeFor(auth.profile?.role), { replaceState: true });
      return;
    }
    if (auth.session && path === '/choose-role' && !needsOnboarding()) {
      goto(homeFor(auth.profile?.role), { replaceState: true });
      return;
    }
    if (auth.session && needsOnboarding() && path !== '/choose-role') {
      goto('/choose-role', { replaceState: true });
      return;
    }
    if (auth.session && !allowed(path, auth.profile?.role)) {
      goto(homeFor(auth.profile?.role), { replaceState: true });
    }
  });

  $effect(() => {
    if (!browser || !auth.ready) return;
    const path = page.url.pathname;
    if (!auth.session && !PUBLIC.includes(path)) goto('/login', { replaceState: true });
    else if (auth.session && path === '/login') goto(homeFor(auth.profile?.role), { replaceState: true });
    else if (auth.session && path === '/choose-role' && !needsOnboarding()) goto(homeFor(auth.profile?.role), { replaceState: true });
    else if (auth.session && needsOnboarding() && path !== '/choose-role') goto('/choose-role', { replaceState: true });
    else if (auth.session && !allowed(path, auth.profile?.role)) goto(homeFor(auth.profile?.role), { replaceState: true });
  });
</script>

{#if !supabaseConfigured}
  <div style="padding:24px;font-family:Inter,sans-serif;max-width:560px;margin:40px auto;">
    <h1 style="font-size:20px;margin:0 0 8px;">JEEVAN is missing env vars</h1>
    <p style="color:#6B6B6B;line-height:1.5;">
      In Vercel → Settings → Environment Variables add
      <code>VITE_SUPABASE_URL</code>,
      <code>VITE_SUPABASE_ANON_KEY</code>, and
      <code>VITE_BACKEND_URL</code>
      for Production, then Redeploy.
    </p>
  </div>
{:else}
{#if !NO_NAV.includes(page.url.pathname)}
  <TopNav {gpsStatus} />
{/if}

<main
  class="app-shell"
  style="padding-top: {NO_NAV.includes(page.url.pathname) ? 'env(safe-area-inset-top)' : 'calc(104px + env(safe-area-inset-top))'};"
>
  <div class="flex-1 overflow-hidden relative h-full">
    {@render children()}
  </div>
</main>

{#if !NO_NAV.includes(page.url.pathname)}
  <FloatingActions role={auth.profile?.role} />
{/if}

<InstallApp />
{/if}
