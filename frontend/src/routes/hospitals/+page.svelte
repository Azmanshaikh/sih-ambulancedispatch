<script lang="ts">
  import { onMount } from 'svelte';
  import { apiFetch, auth } from '$lib/auth.svelte';
  import { t } from '$lib/i18n.svelte';

  interface Hospital {
    id: number;
    name: string;
    available_beds: number;
    total_beds: number;
    specializations: string[];
    phone: string;
    lat?: number;
    lng?: number;
  }

  let hospitals = $state<Hospital[]>([]);
  let loading = $state(true);
  let savingId = $state<number | null>(null);
  let message = $state('');
  let error = $state('');
  let drafts = $state<Record<number, { available_beds: number; total_beds: number }>>({});

  let myHospitalId = $derived(auth.profile?.hospital_id ?? null);
  let role = $derived(auth.profile?.role);
  let canEditAll = $derived(role === 'main_admin' || (role === 'staff' && myHospitalId == null));

  function canEdit(h: Hospital) {
    if (canEditAll) return true;
    if ((role === 'staff' || role === 'doctor') && myHospitalId === h.id) return true;
    return false;
  }

  async function load() {
    try {
      const response = await apiFetch('/hospitals');
      if (!response.ok) throw new Error('Unable to load hospitals');
      hospitals = await response.json();
      const next: Record<number, { available_beds: number; total_beds: number }> = {};
      for (const h of hospitals) {
        next[h.id] = { available_beds: h.available_beds, total_beds: h.total_beds };
      }
      drafts = next;
    } catch (e) {
      console.error(e);
      error = t('hospitals.loadError');
    } finally {
      loading = false;
    }
  }

  async function saveBeds(h: Hospital) {
    const draft = drafts[h.id];
    if (!draft) return;
    savingId = h.id;
    error = '';
    message = '';
    try {
      const response = await apiFetch(`/hospitals/${h.id}/beds`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          available_beds: Number(draft.available_beds),
          total_beds: Number(draft.total_beds),
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : t('hospitals.updateError'));
      hospitals = hospitals.map((row) => (row.id === h.id ? { ...row, ...data } : row));
      drafts = { ...drafts, [h.id]: { available_beds: data.available_beds, total_beds: data.total_beds } };
      message = t('hospitals.updated', { name: h.name, available: data.available_beds, total: data.total_beds });
    } catch (e: any) {
      error = e?.message || t('hospitals.updateError');
    } finally {
      savingId = null;
    }
  }

  onMount(load);
</script>

<svelte:head><title>{t('hospitals.pageTitle')}</title></svelte:head>

<div class="flex-col h-full overflow-y-auto no-sb">
  <div class="p-8 max-w-5xl mx-auto w-full">
    <div class="mb-7 flex justify-between items-end flex-wrap gap-3">
      <div>
        <h1 class="text-4xl font-black tracking-tight uppercase text-black">{t('hospitals.title')}</h1>
        <p class="text-[#4B4B4B] text-xs font-bold uppercase tracking-widest mt-1">{t('hospitals.subtitle')}</p>
        {#if (role === 'staff' || role === 'doctor') && auth.profile?.hospital_name}
          <p class="text-xs font-bold mt-2">{t('hospitals.yourHospital', { name: auth.profile.hospital_name })}</p>
        {:else if canEditAll}
          <p class="text-xs font-bold mt-2">{t('hospitals.headStaff')}</p>
        {/if}
      </div>
      <div class="nb-chip nb-green" style="color:#fff;">
        <span class="blink">●</span>
        {t('hospitals.aiActive')}
      </div>
    </div>

    {#if message}
      <p class="nb-card p-2 text-sm font-bold mb-4">{message}</p>
    {/if}
    {#if error}
      <p class="nb-card p-2 text-sm font-bold mb-4">{error}</p>
    {/if}

    <div class="space-y-5">
      {#if loading}
        <div class="nb-card p-4 text-sm text-black font-bold">{t('hospitals.fetching')}</div>
      {:else}
        {#each hospitals as h, i}
          <div class="nb-card p-5 flex items-center justify-between flex-wrap gap-3 {myHospitalId === h.id ? 'nb-yellow' : i === 0 ? 'nb-yellow' : ''}">
            <div>
              <h3 class="text-lg font-black text-black flex items-center gap-2 flex-wrap">
                🏥 {h.name}
                {#if myHospitalId === h.id}
                  <span class="nb-chip nb-red" style="color:#fff;">{t('hospitals.yourHospitalBadge')}</span>
                {:else if i === 0 && myHospitalId == null}
                  <span class="nb-chip nb-red" style="color:#fff;">{t('hospitals.topPick')}</span>
                {/if}
              </h3>
              <p class="text-xs text-[#4B4B4B] mt-1 font-semibold">{h.specializations.join(', ')}</p>
              {#if h.lat != null && h.lng != null}
                <p class="text-[11px] text-[#4B4B4B] mt-2 font-mono-tech">{h.lat.toFixed(4)}, {h.lng.toFixed(4)}</p>
              {/if}
            </div>
            <div class="text-right">
              {#if canEdit(h) && drafts[h.id]}
                <div class="flex items-end justify-end gap-2 flex-wrap">
                  <label style="display:flex;flex-direction:column;align-items:flex-end;gap:4px;">
                    <span class="text-[10px] font-bold uppercase tracking-widest">{t('hospitals.available')}</span>
                    <input
                      class="nb-input"
                      type="number"
                      min="0"
                      max={drafts[h.id].total_beds}
                      bind:value={drafts[h.id].available_beds}
                      style="width:88px;text-align:right;padding:8px;"
                    />
                  </label>
                  <span class="text-xs font-black pb-3">/</span>
                  <label style="display:flex;flex-direction:column;align-items:flex-end;gap:4px;">
                    <span class="text-[10px] font-bold uppercase tracking-widest">{t('hospitals.total')}</span>
                    <input
                      class="nb-input"
                      type="number"
                      min="1"
                      bind:value={drafts[h.id].total_beds}
                      style="width:88px;text-align:right;padding:8px;"
                    />
                  </label>
                  <button class="btn btn-primary" style="padding:10px 12px;" disabled={savingId === h.id} onclick={() => saveBeds(h)}>
                    {savingId === h.id ? t('hospitals.saving') : t('hospitals.saveBeds')}
                  </button>
                </div>
              {:else}
                <div class="text-xl font-black text-black">{h.available_beds} <span class="text-xs text-[#4B4B4B]">{t('hospitals.beds', { total: h.total_beds })}</span></div>
              {/if}
              <div class="text-[10px] text-[#4B4B4B] font-bold tracking-widest mt-1">📞 {h.phone}</div>
            </div>
          </div>
        {/each}
      {/if}
    </div>
  </div>
</div>
