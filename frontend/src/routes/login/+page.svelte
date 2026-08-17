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

<div class="h-full flex items-center justify-center p-6">
  <div class="nb-card-lg" style="width:100%;max-width:420px;background:#fff;border:4px solid #111;padding:32px;">
    <div style="display:inline-flex;background:#FF2D2D;border:3px solid #111;box-shadow:4px 4px 0 #111;padding:10px 14px;margin-bottom:18px;">
      <img src="/logo.png" alt="JEEVAN" style="height:64px;width:auto;max-width:100%;object-fit:contain;display:block;" />
    </div>
    <h1 style="margin:0 0 8px;font-size:26px;font-weight:900;text-transform:uppercase;letter-spacing:-0.01em;">Sign in with Gmail</h1>
    <p style="margin:0 0 20px;font-size:13px;color:#4B4B4B;line-height:1.5;font-weight:500;">
      After Google sign-in you choose Patient, Driver, or Staff. Patients enter immediately. Drivers and new staff need an OTP from main staff.
    </p>
    <button class="btn btn-primary" style="width:100%;padding:14px;" disabled={loading} onclick={handleGoogle}>
      {loading ? 'Redirecting…' : 'Continue with Google'}
    </button>
    {#if error}
      <p class="nb-card p-2" style="color:#111;font-size:12px;margin:14px 0 0;font-weight:700;">{error}</p>
    {/if}
  </div>
</div>
