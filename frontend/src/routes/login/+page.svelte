<script lang="ts">
  import { signInWithGoogle } from '$lib/auth.svelte';

  let error = $state('');
  let loading = $state(false);

  async function handleGoogle() {
    loading = true;
    error = '';
    try {
      await signInWithGoogle();
    } catch (e: any) {
      error = e?.message || 'Google sign-in failed. Enable the Google provider in Supabase.';
      loading = false;
    }
  }
</script>

<svelte:head><title>JEEVAN — Sign in</title></svelte:head>

<div class="h-full flex items-center justify-center p-6" style="background:#F5F5F5;">
  <div style="width:100%;max-width:420px;background:#fff;border:2px solid #DC2626;padding:32px;">
    <p style="font-family:Orbitron,sans-serif;font-weight:900;letter-spacing:0.2em;color:#DC2626;margin:0 0 8px;">JEEVAN</p>
    <h1 style="margin:0 0 8px;font-size:22px;">Sign in with Gmail</h1>
    <p style="margin:0 0 20px;font-size:13px;color:#6B6B6B;line-height:1.5;">
      You enter as a <strong>Patient</strong>. Driver and Staff access must be approved by existing staff.
      Your Google session is remembered on this device.
    </p>
    <button class="btn btn-primary" style="width:100%;padding:12px;" disabled={loading} onclick={handleGoogle}>
      {loading ? 'Redirecting…' : 'Continue with Google'}
    </button>
    {#if error}
      <p style="color:#DC2626;font-size:12px;margin:12px 0 0;">{error}</p>
    {/if}
  </div>
</div>
