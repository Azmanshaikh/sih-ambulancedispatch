<script lang="ts">
  import { onMount } from 'svelte';
  import { auth, apiFetch, refreshProfile } from '$lib/auth.svelte';

  const BMSIT = { name: 'BMSIT College, Avalahalli, Yelahanka', lat: 13.1344, lng: 77.5693 };

  let hr = $state(72);
  let spo2 = $state(98);
  let chatInput = $state('');
  let messages = $state<{ role: string; content: string }[]>([
    { role: 'assistant', content: 'I am JEEVAN first-aid assist. Tell me what you feel. For a true emergency, tap Request ambulance.' },
  ]);
  let chatting = $state(false);
  let requesting = $state(false);
  let requestMsg = $state('');
  let roleMsg = $state('');
  let cardiac = $state(false);
  let diabetes = $state(false);
  let epilepsy = $state(false);
  let pregnant = $state(false);

  async function loadVitals() {
    const res = await apiFetch('/accounts/vitals');
    if (!res.ok) return;
    const data = await res.json();
    hr = data.vitals?.heart_rate ?? hr;
    spo2 = data.vitals?.spo2 ?? spo2;
  }

  async function sendChat() {
    const text = chatInput.trim();
    if (!text || chatting) return;
    chatInput = '';
    messages = [...messages, { role: 'user', content: text }];
    chatting = true;
    try {
      const res = await apiFetch('/ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, history: messages.slice(0, -1) }),
      });
      const data = await res.json();
      messages = [...messages, { role: 'assistant', content: data.reply || data.detail || 'No reply' }];
    } catch {
      messages = [...messages, { role: 'assistant', content: 'Could not reach the assistant.' }];
    } finally {
      chatting = false;
    }
  }

  async function requestHelp() {
    requesting = true;
    requestMsg = '';
    try {
      await apiFetch('/accounts/records', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cardiac, diabetes, epilepsy, pregnant }),
      });
      const res = await apiFetch('/tracking/dispatch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          incident_lat: BMSIT.lat,
          incident_lng: BMSIT.lng,
          address: BMSIT.name,
          patient_name: auth.profile?.full_name || auth.profile?.email,
          cardiac,
          diabetes,
          epilepsy,
          pregnant,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Dispatch failed');
      requestMsg = `Ambulance ${data.data?.ambulance_id} assigned → ${data.data?.hospital_name} (${data.data?.eta_minutes} min)`;
    } catch (e: any) {
      requestMsg = e?.message || 'Could not request help';
    } finally {
      requesting = false;
    }
  }

  async function askRole(role: 'driver' | 'staff') {
    roleMsg = '';
    const res = await apiFetch('/accounts/request-role', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ requested_role: role }),
    });
    const data = await res.json();
    if (!res.ok) {
      roleMsg = data.detail || 'Request failed';
      return;
    }
    await refreshProfile();
    roleMsg = `Staff must approve your ${role} access.`;
  }

  onMount(() => {
    loadVitals();
    const t = setInterval(loadVitals, 2000);
    return () => clearInterval(t);
  });
</script>

<svelte:head><title>JEEVAN — Patient</title></svelte:head>

<div class="h-full overflow-y-auto p-6" style="background:#F5F5F5;">
  <div class="max-w-5xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-5">
    <section class="bg-white border-2 border-[#E0E0E0] p-5">
      <h2 class="text-sm font-black uppercase tracking-widest text-red-600 mb-1">Heartbeat (mock sensor)</h2>
      <p class="text-[10px] text-slate-500 uppercase mb-4">Random walk vitals for demo — staff sees the same feed</p>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <div class="text-4xl font-black text-[#1A1A1A]">{hr}<span class="text-sm text-slate-500 ml-1">bpm</span></div>
          <div class="text-[10px] uppercase tracking-widest text-slate-500">Heart rate</div>
        </div>
        <div>
          <div class="text-4xl font-black text-[#1A1A1A]">{spo2}<span class="text-sm text-slate-500 ml-1">%</span></div>
          <div class="text-[10px] uppercase tracking-widest text-slate-500">SpO2</div>
        </div>
      </div>
    </section>

    <section class="bg-white border-2 border-[#E0E0E0] p-5">
      <h2 class="text-sm font-black uppercase tracking-widest text-red-600 mb-3">Request ambulance</h2>
      <p class="text-xs text-slate-500 mb-3">Pickup defaults to BMSIT College, Yelahanka.</p>
      <div class="grid grid-cols-2 gap-2 text-xs mb-3">
        <label><input type="checkbox" bind:checked={cardiac} /> Cardiac history</label>
        <label><input type="checkbox" bind:checked={diabetes} /> Diabetes</label>
        <label><input type="checkbox" bind:checked={epilepsy} /> Epilepsy</label>
        <label><input type="checkbox" bind:checked={pregnant} /> Pregnant</label>
      </div>
      <button class="btn btn-primary" style="width:100%;padding:12px;" disabled={requesting} onclick={requestHelp}>
        {requesting ? 'Dispatching…' : 'Request ambulance'}
      </button>
      {#if requestMsg}<p class="text-xs mt-2 text-slate-700">{requestMsg}</p>{/if}
    </section>

    <section class="bg-white border-2 border-[#E0E0E0] p-5 lg:col-span-2 flex flex-col" style="min-height:280px;">
      <h2 class="text-sm font-black uppercase tracking-widest text-red-600 mb-3">AI chatbot</h2>
      <div class="flex-1 overflow-y-auto space-y-2 mb-3" style="max-height:240px;">
        {#each messages as m}
          <div class="text-sm p-2 {m.role === 'user' ? 'bg-red-50 text-right' : 'bg-slate-100'}">{m.content}</div>
        {/each}
      </div>
      <div class="flex gap-2">
        <input class="flex-1 border-2 border-[#E0E0E0] px-3 py-2 text-sm" bind:value={chatInput} placeholder="Describe symptoms…" onkeydown={(e) => e.key === 'Enter' && sendChat()} />
        <button class="btn btn-primary" onclick={sendChat} disabled={chatting}>Send</button>
      </div>
    </section>

    <section class="bg-white border-2 border-[#E0E0E0] p-5 lg:col-span-2">
      <h2 class="text-sm font-black uppercase tracking-widest text-slate-600 mb-2">Need Driver or Staff access?</h2>
      {#if auth.profile?.requested_role}
        <p class="text-xs text-amber-700">Waiting for staff approval: {auth.profile.requested_role}</p>
      {:else}
        <div class="flex gap-2">
          <button class="btn btn-secondary" onclick={() => askRole('driver')}>Request driver</button>
          <button class="btn btn-secondary" onclick={() => askRole('staff')}>Request staff</button>
        </div>
      {/if}
      {#if roleMsg}<p class="text-xs mt-2">{roleMsg}</p>{/if}
    </section>
  </div>
</div>
