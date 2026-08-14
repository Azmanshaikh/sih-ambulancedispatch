<script lang="ts">
  import '../app.css';
  import TopNav from '$lib/components/TopNav.svelte';
  import InstallApp from '$lib/components/InstallApp.svelte';
  import type { Snippet } from 'svelte';
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { auth, homeFor, initAuth, needsOnboarding } from '$lib/auth.svelte';

  interface Props { children: Snippet; }
  let { children }: Props = $props();

  let gpsStatus = $state('BMSIT College, Yelahanka');

  const PUBLIC = ['/login', '/auth/callback'];
  const NO_NAV = ['/login', '/auth/callback', '/choose-role'];

  const STAFF_PATHS = ['/', '/request', '/navigation', '/hospitals', '/notifications', '/staff/approvals'];
  const PATIENT_PATHS = ['/patient', '/ai-guide', '/ai-call'];
  const DRIVER_PATHS = ['/driver', '/hospitals'];

  function allowed(pathname: string, role?: string | null) {
    if (PUBLIC.includes(pathname)) return true;
    if (needsOnboarding()) return pathname === '/choose-role';
    if (role === 'staff') return STAFF_PATHS.includes(pathname) || pathname.startsWith('/staff/');
    if (role === 'driver') return DRIVER_PATHS.includes(pathname);
    return PATIENT_PATHS.includes(pathname);
  }

  onMount(async () => {
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
    if (!auth.ready) return;
    const path = page.url.pathname;
    if (!auth.session && !PUBLIC.includes(path)) goto('/login', { replaceState: true });
    else if (auth.session && path === '/login') goto(homeFor(auth.profile?.role), { replaceState: true });
    else if (auth.session && path === '/choose-role' && !needsOnboarding()) goto(homeFor(auth.profile?.role), { replaceState: true });
    else if (auth.session && needsOnboarding() && path !== '/choose-role') goto('/choose-role', { replaceState: true });
    else if (auth.session && !allowed(path, auth.profile?.role)) goto(homeFor(auth.profile?.role), { replaceState: true });
  });
</script>

{#if !NO_NAV.includes(page.url.pathname)}
  <TopNav {gpsStatus} />
{/if}

<main
  class="app-shell"
  style="padding-top: {NO_NAV.includes(page.url.pathname) ? 'env(safe-area-inset-top)' : 'calc(88px + env(safe-area-inset-top))'};"
>
  <div class="flex-1 overflow-hidden relative h-full">
    {@render children()}
  </div>
</main>

<InstallApp />
