<script lang="ts">
  import { signInWithGoogle, signInWithPassword, signUpWithPassword } from '$lib/auth.svelte';
  import { t } from '$lib/i18n.svelte';
  import LanguageSettings from '$lib/components/LanguageSettings.svelte';

  let error = $state('');
  let info = $state('');
  let loading = $state(false);
  let email = $state('');
  let password = $state('');

  async function handleGoogle() {
    loading = true;
    error = '';
    info = '';
    try {
      await signInWithGoogle();
    } catch (e: any) {
      error = e?.message || t('login.googleFailed');
      loading = false;
    }
  }

  async function handlePassword(create: boolean) {
    loading = true;
    error = '';
    info = '';
    try {
      if (create) {
        const data = await signUpWithPassword(email.trim(), password);
        if (!data.session) {
          info = t('login.checkEmail');
          loading = false;
          return;
        }
      } else {
        await signInWithPassword(email.trim(), password);
      }
    } catch (e: any) {
      error = e?.message || t('login.passwordFailed');
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
    <form class="login-form" onsubmit={(e) => { e.preventDefault(); handlePassword(false); }}>
      <label class="login-label">
        {t('login.email')}
        <input class="login-input" type="email" autocomplete="username" bind:value={email} required />
      </label>
      <label class="login-label">
        {t('login.password')}
        <input class="login-input" type="password" autocomplete="current-password" bind:value={password} required minlength="6" />
      </label>
      <button class="btn btn-primary login-btn" type="submit" disabled={loading}>
        {loading ? t('login.redirecting') : t('login.signIn')}
      </button>
      <button class="btn login-btn" type="button" disabled={loading} onclick={() => handlePassword(true)}>
        {t('login.createAccount')}
      </button>
    </form>
    <p class="login-or">{t('login.or')}</p>
    <button class="btn btn-primary login-btn" disabled={loading} onclick={handleGoogle}>
      {loading ? t('login.redirecting') : t('login.continue')}
    </button>
    {#if error}
      <p class="login-error">{error}</p>
    {/if}
    {#if info}
      <p class="login-info">{info}</p>
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
  .login-form {
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-bottom: 12px;
  }
  .login-label {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: 12px;
    font-weight: 700;
    color: var(--clr-muted);
  }
  .login-input {
    padding: 10px 12px;
    border: 2px solid #111;
    border-radius: var(--radius-sm);
    font-size: 14px;
  }
  .login-or {
    text-align: center;
    font-size: 12px;
    font-weight: 700;
    color: var(--clr-muted);
    margin: 4px 0 12px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
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
  .login-info {
    color: var(--clr-ink);
    font-size: 13px;
    margin: 14px 0 0;
    font-weight: 600;
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
