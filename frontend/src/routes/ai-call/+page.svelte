<script lang="ts">
  import { onDestroy } from 'svelte';
  import { apiFetch } from '$lib/auth.svelte';

  let conversationUrl = $state('');
  let conversationId = $state('');
  let loading = $state(false);
  let saving = $state(false);
  let error = $state('');
  let savedNote = $state('');

  async function startCall() {
    loading = true;
    error = '';
    savedNote = '';
    try {
      const res = await apiFetch('/ai/tavus/start', { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not start Tavus call');
      conversationUrl = data.conversation_url;
      conversationId = data.conversation_id || '';
    } catch (e: any) {
      error = e?.message || 'Could not start Tavus call. Add TAVUS_API_KEY to .env.';
    } finally {
      loading = false;
    }
  }

  async function endCall() {
    const id = conversationId;
    conversationUrl = '';
    conversationId = '';
    if (!id) return;
    saving = true;
    try {
      const res = await apiFetch(`/ai/tavus/${id}/end`, { method: 'POST' });
      const data = await res.json();
      const n = data.saved || 0;
      savedNote = n
        ? `Saved ${n} spoken turns for your future trip report.`
        : 'Call ended. Transcript may still arrive shortly and will be stored for reports.';
    } catch {
      savedNote = 'Call ended.';
    } finally {
      saving = false;
    }
  }

  onDestroy(() => {
    if (conversationId) {
      apiFetch(`/ai/tavus/${conversationId}/end`, { method: 'POST' });
    }
  });
</script>

<svelte:head><title>JEEVAN — AI video call</title></svelte:head>

<div class="h-full flex flex-col" style="background:#0B1220;color:#fff;">
  {#if conversationUrl}
    <div class="flex items-center justify-between px-4 py-2 border-b border-slate-800">
      <p class="text-[10px] uppercase tracking-[0.3em] text-red-400 font-black">Tavus · listens · thinks · answers</p>
      <button class="btn btn-primary px-4 py-2" disabled={saving} onclick={endCall}>
        {saving ? 'Saving transcript…' : 'End call'}
      </button>
    </div>
    <iframe
      title="JEEVAN Tavus call"
      src={conversationUrl}
      allow="camera; microphone; fullscreen; display-capture; autoplay"
      class="flex-1 w-full border-0"
    ></iframe>
  {:else}
    <div class="flex-1 flex flex-col items-center justify-center p-8 text-center">
      <p class="text-[10px] uppercase tracking-[0.3em] text-red-400 font-black mb-2">AI video call</p>
      <h1 class="text-3xl font-black mb-3">Talk to JEEVAN</h1>
      <p class="text-sm text-slate-300 max-w-md mb-6">
        Allow camera and mic. The avatar hears you, thinks, then answers with simple remedies.
        What you both say is stored and used in the hospital trip report after dispatch.
      </p>
      {#if error}<p class="text-xs text-red-400 mb-4 max-w-lg">{error}</p>{/if}
      {#if savedNote}<p class="text-xs text-green-400 mb-4">{savedNote}</p>{/if}
      <button class="btn btn-primary px-10 py-3" disabled={loading || saving} onclick={startCall}>
        {loading ? 'Connecting…' : 'Start video call'}
      </button>
    </div>
  {/if}
</div>
