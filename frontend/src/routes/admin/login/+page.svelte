<script lang="ts">
  import { signInWithGoogleAdmin, MAIN_ADMIN_EMAIL } from '$lib/auth.svelte';
  import LanguageSettings from '$lib/components/LanguageSettings.svelte';
  import { page } from '$app/state';

  let error = $state('');
  let loading = $state(false);

  $effect(() => {
    if (page.url.searchParams.get('error') === 'not_allowed') {
      error = `Access denied. Main Admin sign-in is restricted to ${MAIN_ADMIN_EMAIL}.`;
    }
  });

  async function handleAdminGoogle() {
    loading = true;
    error = '';
    try {
      await signInWithGoogleAdmin();
    } catch (e: any) {
      error = e?.message || 'Google sign-in failed.';
      loading = false;
    }
  }
</script>

<svelte:head><title>JEEVAN — Main Admin Sign In</title></svelte:head>

<div class="admin-login-page">
  <div class="lang-wrap">
    <LanguageSettings />
  </div>
  <div class="nb-card-lg login-card">
    <div class="admin-badge">
      <span class="material-symbols-outlined">admin_panel_settings</span>
      Main Admin
    </div>
    <div class="login-logo-wrap">
      <img src="/logo.png" alt="JEEVAN" class="login-logo" />
    </div>
    <h1 class="login-title">Main Admin Sign In</h1>
    <p class="login-body">
      Route simulation and admin tools are restricted to the authorized Main Admin account
      (<strong>{MAIN_ADMIN_EMAIL}</strong>).
    </p>
    <button class="btn btn-primary login-btn" disabled={loading} onclick={handleAdminGoogle}>
      {loading ? 'Redirecting…' : 'Continue with Google'}
    </button>
    {#if error}
      <p class="login-error">{error}</p>
    {/if}
    <a href="/login" class="back-link">← Standard user sign in</a>
  </div>
</div>

<style>
  .admin-login-page {
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
    position: relative;
    background: linear-gradient(180deg, #eff6ff 0%, var(--clr-bg) 100%);
  }
  .lang-wrap {
    position: absolute;
    top: 16px;
    right: 16px;
    z-index: 20;
  }
  .login-card {
    width: 100%;
    max-width: 440px;
    padding: 32px;
  }
  .admin-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    margin-bottom: 14px;
    border-radius: 999px;
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    color: var(--clr-primary);
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .admin-badge .material-symbols-outlined {
    font-size: 18px;
  }
  .login-logo-wrap {
    display: inline-flex;
    background: var(--clr-primary);
    border-radius: var(--radius-md);
    padding: 12px 16px;
    margin-bottom: 18px;
  }
  .login-logo {
    height: 56px;
    width: auto;
    max-width: 100%;
    object-fit: contain;
    display: block;
    filter: brightness(0) invert(1);
  }
  .login-title {
    margin: 0 0 8px;
    font-size: 24px;
    font-weight: 800;
    color: var(--clr-ink);
  }
  .login-body {
    margin: 0 0 20px;
    font-size: 14px;
    color: var(--clr-muted);
    line-height: 1.55;
  }
  .login-body strong {
    color: var(--clr-ink);
    font-weight: 600;
  }
  .login-btn {
    width: 100%;
    padding: 14px;
  }
  .login-error {
    color: var(--clr-danger);
    font-size: 13px;
    margin: 14px 0 0;
    font-weight: 600;
    padding: 10px 12px;
    background: var(--clr-danger-bg);
    border-radius: var(--radius-sm);
  }
  .back-link {
    display: inline-block;
    margin-top: 16px;
    font-size: 13px;
    color: var(--clr-primary);
    text-decoration: none;
    font-weight: 600;
  }
  .back-link:hover {
    text-decoration: underline;
  }
</style>
