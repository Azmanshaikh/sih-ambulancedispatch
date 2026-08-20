<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { supabase } from '$lib/supabase';
  import { auth, homeFor, refreshProfile, consumeAdminLoginIntent, isMainAdmin, signOut } from '$lib/auth.svelte';

  let message = $state('Finishing Google sign-in…');

  onMount(async () => {
    try {
      const href = window.location.href;
      if (href.includes('code=')) {
        const { error } = await supabase.auth.exchangeCodeForSession(href);
        if (error) throw error;
      }
      const { data } = await supabase.auth.getSession();
      auth.session = data.session;
      if (!auth.session) throw new Error('No session');
      await refreshProfile();
      const adminIntent = consumeAdminLoginIntent();
      if (adminIntent) {
        if (!isMainAdmin(auth.profile)) {
          await signOut();
          goto('/admin/login?error=not_allowed', { replaceState: true });
          return;
        }
        goto('/admin/simulation', { replaceState: true });
        return;
      }
      goto(homeFor(auth.profile?.role), { replaceState: true });
    } catch (e: any) {
      message = e?.message || 'Sign-in failed';
      setTimeout(() => goto('/login'), 1600);
    }
  });
</script>

<svelte:head><title>JEEVAN — Auth</title></svelte:head>

<div class="h-full flex items-center justify-center p-6">
  <p class="nb-card nb-yellow px-6 py-4 text-sm font-black uppercase tracking-widest text-black">{message}</p>
</div>
