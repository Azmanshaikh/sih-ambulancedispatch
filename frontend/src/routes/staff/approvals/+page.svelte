<script lang="ts">
  import { onMount } from 'svelte';
  import { apiFetch } from '$lib/auth.svelte';

  let otps = $state<any[]>([]);
  let profiles = $state<any[]>([]);
  let message = $state('');

  async function load() {
    const [otpRes, reqRes] = await Promise.all([apiFetch('/accounts/otps'), apiFetch('/accounts/requests')]);
    if (otpRes.ok) {
      const data = await otpRes.json();
      otps = data.otps || [];
    }
    if (reqRes.ok) {
      const data = await reqRes.json();
      profiles = data.profiles || [];
    }
  }

  onMount(() => {
    load();
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  });
</script>

<svelte:head><title>JEEVAN — Access OTPs</title></svelte:head>

<div class="h-full overflow-y-auto p-8" style="background:#F5F5F5;">
  <div class="max-w-4xl mx-auto">
    <h1 class="text-2xl font-black uppercase tracking-tight mb-2">Access OTPs</h1>
    <p class="text-xs text-slate-500 uppercase tracking-widest mb-6">
      Drivers and new staff must ask you for this code. Do not share it unless you know them.
    </p>
    {#if message}<p class="text-sm text-red-600 mb-3">{message}</p>{/if}

    {#if otps.length === 0}
      <p class="text-sm text-slate-500">No pending OTPs.</p>
    {:else}
      <div class="space-y-3">
        {#each otps as o}
          <div class="bg-white border-2 border-[#DC2626] p-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p class="font-bold">{o.full_name || o.email}</p>
              <p class="text-xs text-slate-500">{o.email} · wants <strong>{o.requested_role}</strong></p>
            </div>
            <div class="text-right">
              <p class="text-[10px] uppercase tracking-widest text-slate-500">OTP</p>
              <p class="text-3xl font-black tracking-[0.3em] text-red-600">{o.code}</p>
            </div>
          </div>
        {/each}
      </div>
    {/if}

    <h2 class="text-sm font-black uppercase tracking-widest mt-10 mb-3 text-slate-600">Directory</h2>
    <div class="space-y-2">
      {#each profiles as p}
        <div class="text-xs flex justify-between bg-white border border-[#E0E0E0] px-3 py-2">
          <span>{p.full_name || p.email}</span>
          <span class="uppercase font-bold">{p.role}{p.status === 'pending' ? ' · pending OTP' : ''}{p.ambulance_id ? ` · ${p.ambulance_id}` : ''}</span>
        </div>
      {/each}
    </div>
  </div>
</div>
