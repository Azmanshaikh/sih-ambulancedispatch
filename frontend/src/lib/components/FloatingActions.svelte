<script lang="ts">
  import { page } from '$app/state';
  import { t } from '$lib/i18n.svelte';

  interface Props {
    role?: string | null;
  }

  let { role = 'patient' }: Props = $props();

  const HIDE_ON = ['/ai-guide', '/ai-call'];
  let show = $derived(role === 'patient' && !HIDE_ON.includes(page.url.pathname));
</script>

{#if show}
  <div class="fab-stack">
    <a href="/ai-call" class="fab nb-blue" aria-label={t('patient.videoCall')}>
      <span class="material-symbols-outlined">videocam</span>
      <span>{t('fab.video')}</span>
    </a>
    <a href="/ai-guide" class="fab nb-yellow" aria-label={t('patient.chatbot')}>
      <span class="material-symbols-outlined">forum</span>
      <span>{t('fab.chat')}</span>
    </a>
  </div>
{/if}
