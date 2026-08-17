<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { supabase } from '$lib/supabase';
  import { auth, homeFor, refreshProfile } from '$lib/auth.svelte';

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
