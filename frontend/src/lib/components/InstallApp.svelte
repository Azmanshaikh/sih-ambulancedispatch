<script lang="ts">
  import { browser } from '$app/environment';
  import { onMount } from 'svelte';

  let deferred: any = $state(null);
  let visible = $state(false);
  let iosHint = $state(false);
  let standalone = $state(false);

  function isStandalone() {
    if (!browser) return false;
    const nav = window.navigator as Navigator & { standalone?: boolean };
    return window.matchMedia('(display-mode: standalone)').matches || nav.standalone === true;
  }

  function isIos() {
    if (!browser) return false;
    return /iphone|ipad|ipod/i.test(window.navigator.userAgent);
  }

  onMount(() => {
    if (import.meta.env.DEV && 'serviceWorker' in navigator) {
      navigator.serviceWorker.register('/dev-sw.js').catch(() => {});
    }
    if (standalone) return;
    if (sessionStorage.getItem('jeevan-install-dismissed') === '1') return;

    if (isIos()) {
      iosHint = true;
      visible = true;
      return;
    }

    const onPrompt = (e: Event) => {
      e.preventDefault();
      deferred = e;
      visible = true;
    };
    window.addEventListener('beforeinstallprompt', onPrompt);
    window.addEventListener('appinstalled', () => {
      visible = false;
      deferred = null;
      standalone = true;
    });
    return () => window.removeEventListener('beforeinstallprompt', onPrompt);
  });

  async function install() {
    if (!deferred?.prompt) return;
    deferred.prompt();
    await deferred.userChoice;
    deferred = null;
    visible = false;
  }

  function dismiss() {
    visible = false;
    sessionStorage.setItem('jeevan-install-dismissed', '1');
  }
</script>

{#if visible && !standalone}
  <div class="install-banner">
    <img src="/icon-192.png" alt="" width="40" height="40" />
    <div class="install-copy">
      <p class="install-title">Install JEEVAN</p>
      {#if iosHint}
        <p class="install-sub">Safari → Share → Add to Home Screen</p>
      {:else}
        <p class="install-sub">Add to your phone home screen</p>
      {/if}
    </div>
    {#if deferred}
      <button class="btn btn-primary" type="button" onclick={install}>Install</button>
    {/if}
    <button class="btn btn-ghost" type="button" onclick={dismiss}>Not now</button>
  </div>
{/if}

<style>
  .install-banner {
    position: fixed;
    left: 12px;
    right: 12px;
    bottom: calc(12px + env(safe-area-inset-bottom));
    z-index: 80;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 14px;
    background: #ffffff;
    border: 3px solid #111;
    box-shadow: 6px 6px 0 #111;
  }
  .install-banner img {
    border: 2px solid #111;
    flex-shrink: 0;
  }
  .install-copy {
    flex: 1;
    min-width: 0;
  }
  .install-title {
    margin: 0;
    font-family: 'Rajdhani', sans-serif;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-size: 13px;
    color: #1a1a1a;
  }
  .install-sub {
    margin: 2px 0 0;
    font-size: 11px;
    color: #6b6b6b;
  }
</style>
