<script lang="ts">
  import { onMount } from 'svelte';
  import { apiFetch } from '$lib/auth.svelte';

  let messages = $state<{ role: string; content: string }[]>([]);
  let draft = $state('');
  let sending = $state(false);
  let error = $state('');

  async function loadHistory() {
    const res = await apiFetch('/ai/chat/history');
    if (!res.ok) return;
    const data = await res.json();
    messages = (data.messages || []).map((m: any) => ({ role: m.role, content: m.content }));
  }

  async function send() {
    const text = draft.trim();
    if (!text || sending) return;
    sending = true;
    error = '';
    draft = '';
    messages = [...messages, { role: 'user', content: text }];
    try {
      const res = await apiFetch('/ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Chat failed');
      messages = [...messages, { role: 'assistant', content: data.reply }];
    } catch (e: any) {
      error = e?.message || 'Chat failed';
    } finally {
      sending = false;
    }
  }

  onMount(loadHistory);
</script>

<svelte:head><title>JEEVAN — AI Chat</title></svelte:head>

<div class="h-full flex flex-col p-4" style="background:#F5F5F5;">
  <div class="max-w-3xl mx-auto w-full flex flex-col h-full">
    <h1 class="text-xl font-black uppercase tracking-tight mb-1">Everyday health chat</h1>
    <p class="text-xs text-slate-500 mb-4">Ask about common issues. This is not a doctor. Chats are saved for your future trip report. Use Emergency SOS if you are in danger.</p>
    <div class="flex-1 overflow-y-auto bg-white border-2 border-[#E0E0E0] p-4 space-y-3">
      {#if messages.length === 0}
        <p class="text-sm text-slate-500">Try: “I have a mild headache after work” or “What should I eat when I have a fever?”</p>
      {/if}
      {#each messages as m}
        <div class="text-sm {m.role === 'user' ? 'text-right' : ''}">
          <span class="inline-block max-w-[85%] p-3 {m.role === 'user' ? 'bg-red-600 text-white' : 'bg-slate-100'}">{m.content}</span>
        </div>
      {/each}
    </div>
    {#if error}<p class="text-xs text-red-600 mt-2">{error}</p>{/if}
    <form class="mt-3 flex gap-2" onsubmit={(e) => { e.preventDefault(); send(); }}>
      <input
        class="flex-1 border-2 border-[#E0E0E0] p-3"
        bind:value={draft}
        placeholder="Describe an everyday issue…"
        disabled={sending}
      />
      <button class="btn btn-primary px-5" disabled={sending}>{sending ? '…' : 'Send'}</button>
    </form>
  </div>
</div>
