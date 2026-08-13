<script lang="ts">
  import { onMount } from 'svelte';
  import { apiFetch } from '$lib/auth.svelte';

  let requests = $state<any[]>([]);
  let profiles = $state<any[]>([]);
  let ambulances = $state<any[]>([]);
  let message = $state('');

  async function load() {
    const res = await apiFetch('/accounts/requests');
    if (!res.ok) return;
    const data = await res.json();
    requests = data.requests || [];
    profiles = data.profiles || [];
    const fleet = await apiFetch('/tracking/fleet');
    if (fleet.ok) {
      const f = await fleet.json();
      ambulances = f.ambulances || [];
    }
  }

  async function decide(id: string, approve: bool, ambulance_id: string | null = null) {
    message = '';
    const res = await apiFetch(`/accounts/requests/${id}/decide`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approve, ambulance_id }),
    });
    const data = await res.json();
    if (!res.ok) {
      message = data.detail || 'Failed';
      return;
    }
    message = approve ? 'Approved' : 'Denied';
    await load();
  }

  onMount(load);
</script>

<svelte:head><title>JEEVAN — Approvals</title></svelte:head>

<div class="h-full overflow-y-auto p-8" style="background:#F5F5F5;">
  <div class="max-w-4xl mx-auto">
    <h1 class="text-2xl font-black uppercase tracking-tight mb-2">Role approvals</h1>
    <p class="text-xs text-slate-500 uppercase tracking-widest mb-6">Patients may request Driver or Staff. Only staff can approve.</p>
    {#if message}<p class="text-sm text-red-600 mb-3">{message}</p>{/if}

    {#if requests.length === 0}
      <p class="text-sm text-slate-500">No pending requests.</p>
    {:else}
      <div class="space-y-3">
        {#each requests as r}
          <div class="bg-white border-2 border-[#E0E0E0] p-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p class="font-bold">{r.full_name || r.email}</p>
              <p class="text-xs text-slate-500">{r.email} · wants <strong>{r.requested_role}</strong></p>
            </div>
            <div class="flex gap-2 items-center">
              {#if r.requested_role === 'driver'}
                <select class="border-2 border-[#E0E0E0] text-xs p-1" id="amb-{r.id}">
                  <option value="">Unit…</option>
                  {#each ambulances as a}
                    <option value={a.id}>{a.id} · {a.label}</option>
                  {/each}
                </select>
              {/if}
              <button
                class="btn btn-primary"
                onclick={() => {
                  const sel = document.getElementById(`amb-${r.id}`) as HTMLSelectElement | null;
                  decide(String(r.id), true, sel?.value || null);
                }}
              >Approve</button>
              <button class="btn btn-ghost" onclick={() => decide(String(r.id), false)}>Deny</button>
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
          <span class="uppercase font-bold">{p.role}{p.ambulance_id ? ` · ${p.ambulance_id}` : ''}</span>
        </div>
      {/each}
    </div>
  </div>
</div>
