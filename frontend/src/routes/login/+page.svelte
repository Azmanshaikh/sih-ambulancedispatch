<script lang="ts">
  import { signInWithGoogle } from '$lib/auth.svelte';
  import { t } from '$lib/i18n.svelte';
  import LanguageSettings from '$lib/components/LanguageSettings.svelte';

  let error = $state('');
  let loading = $state(false);

  async function handleGoogle() {
    loading = true;
    error = '';
    try {
      await signInWithGoogle();
    } catch (e: any) {
      error = e?.message || t('login.googleFailed');
      loading = false;
    }
  }
</script>

<svelte:head><title>{t('login.pageTitle')}</title></svelte:head>

<div class="h-full flex items-center justify-center p-6" style="position:relative;">
  <div style="position:absolute;top:16px;right:16px;z-index:20;">
    <LanguageSettings />
  </div>
  <div class="nb-card-lg login-card">
    <div class="login-logo-wrap">
      <img src="/logo.png" alt="JEEVAN" class="login-logo" />
    </div>
    <h1 class="login-title">{t('login.title')}</h1>
    <p class="login-body">{t('login.body')}</p>
    <button class="btn btn-primary login-btn" disabled={loading} onclick={handleGoogle}>
      {loading ? t('login.redirecting') : t('login.continue')}
    </button>
    {#if error}
      <p class="login-error">{error}</p>
    {/if}
    <a href="/admin/login" class="admin-link">Main Admin sign in →</a>
  </div>
</div>

<style>
  .login-card {
    width: 100%;
    max-width: 420px;
    padding: 32px;
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
  .admin-link {
    display: inline-block;
    margin-top: 18px;
    font-size: 13px;
    color: var(--clr-primary);
    text-decoration: none;
    font-weight: 600;
  }
  .admin-link:hover {
    text-decoration: underline;
  }
</style>
