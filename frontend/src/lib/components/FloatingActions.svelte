<script lang="ts">
  import { page } from '$app/state';

  interface Props {
    role?: string | null;
  }

  let { role = 'patient' }: Props = $props();

  const HIDE_ON = ['/ai-guide', '/ai-call'];
  let show = $derived(role === 'patient' && !HIDE_ON.includes(page.url.pathname));
</script>

{#if show}
  <div class="fab-stack">
    <a href="/ai-call" class="fab nb-blue" style="color:#fff;" aria-label="Start AI video call">
      <span class="material-symbols-outlined">videocam</span>
      <span>Video Call</span>
    </a>
    <a href="/ai-guide" class="fab nb-yellow" aria-label="Open AI chatbot">
      <span class="material-symbols-outlined">forum</span>
      <span>AI Chatbot</span>
    </a>
  </div>
{/if}
