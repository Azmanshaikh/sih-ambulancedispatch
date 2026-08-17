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

<div class="h-full flex flex-col p-4">
  <div class="max-w-3xl mx-auto w-full flex flex-col h-full">
    <div class="nb-card nb-yellow p-4 mb-3 flex items-center gap-3">
      <span class="material-symbols-outlined" style="font-size:32px;">forum</span>
      <div>
        <h1 class="text-xl font-black uppercase tracking-tight leading-none">AI Chatbot</h1>
        <p class="text-[11px] text-black font-semibold mt-1">Ask about everyday issues. Not a doctor. Chats are saved for your trip report. Use SOS if in danger.</p>
      </div>
    </div>
    <div class="flex-1 overflow-y-auto no-sb nb-card p-4 space-y-3">
      {#if messages.length === 0}
        <p class="text-sm text-[#4B4B4B] font-semibold">Try: “I have a mild headache after work” or “What should I eat when I have a fever?”</p>
      {/if}
      {#each messages as m}
        <div class="text-sm {m.role === 'user' ? 'text-right' : ''}">
          <span class="inline-block max-w-[85%] p-3 font-semibold {m.role === 'user' ? 'nb-red' : 'nb-flat'}" style="{m.role === 'user' ? 'color:#fff;' : ''}box-shadow:3px 3px 0 #111;">{m.content}</span>
        </div>
      {/each}
    </div>
    {#if error}<p class="text-xs text-[#FF2D2D] font-black mt-2">{error}</p>{/if}
    <form class="mt-3 flex gap-2" onsubmit={(e) => { e.preventDefault(); send(); }}>
      <input
        class="nb-input flex-1"
        bind:value={draft}
        placeholder="Describe an everyday issue…"
        disabled={sending}
      />
      <button class="btn btn-primary px-5" disabled={sending}>{sending ? '…' : 'Send'}</button>
    </form>
  </div>
</div>
