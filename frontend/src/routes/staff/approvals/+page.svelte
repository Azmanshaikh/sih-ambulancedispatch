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

<div class="h-full overflow-y-auto no-sb p-8">
  <div class="max-w-4xl mx-auto">
    <h1 class="text-3xl font-black uppercase tracking-tight mb-2 text-black">Access OTPs</h1>
    <p class="text-xs text-[#4B4B4B] uppercase tracking-widest mb-6 font-bold">
      Drivers and new staff must ask you for this code. Do not share it unless you know them.
    </p>
    {#if message}<p class="nb-card p-2 text-sm text-black mb-3 font-bold">{message}</p>{/if}

    {#if otps.length === 0}
      <p class="nb-card p-3 text-sm text-black font-semibold">No pending OTPs.</p>
    {:else}
      <div class="space-y-3">
        {#each otps as o}
          <div class="nb-card p-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p class="font-black text-black">{o.full_name || o.email}</p>
              <p class="text-xs text-[#4B4B4B] font-semibold">{o.email} · wants <strong>{o.requested_role}</strong></p>
            </div>
            <div class="text-right nb-yellow p-2" style="border:3px solid #111;">
              <p class="text-[10px] uppercase tracking-widest text-black font-bold">OTP</p>
              <p class="text-3xl font-black tracking-[0.3em] text-black">{o.code}</p>
            </div>
          </div>
        {/each}
      </div>
    {/if}

    <h2 class="nb-chip nb-blue mt-10 mb-3" style="color:#fff;">Directory</h2>
    <div class="space-y-2">
      {#each profiles as p}
        <div class="text-xs flex justify-between nb-flat px-3 py-2 font-semibold">
          <span>{p.full_name || p.email}</span>
          <span class="uppercase font-black">{p.role}{p.status === 'pending' ? ' · pending OTP' : ''}{p.ambulance_id ? ` · ${p.ambulance_id}` : ''}</span>
        </div>
      {/each}
    </div>
  </div>
</div>
