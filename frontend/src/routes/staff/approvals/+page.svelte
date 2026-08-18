<script lang="ts">
  import { onMount } from 'svelte';
  import { apiFetch } from '$lib/auth.svelte';
  import { roleLabel, t } from '$lib/i18n.svelte';

  let otps = $state<any[]>([]);
  let profiles = $state<any[]>([]);
  let message = $state('');
  let loadError = $state('');

  async function load() {
    const [otpRes, reqRes] = await Promise.all([apiFetch('/accounts/otps'), apiFetch('/accounts/requests')]);
    if (otpRes.ok) {
      const data = await otpRes.json();
      otps = data.otps || [];
      loadError = '';
    } else {
      loadError = t('otp.loadError');
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

  let pendingProfiles = $derived(
    profiles.filter((p) => p.status === 'pending' && p.requested_role && !otps.some((o) => o.user_id === p.id || o.email === p.email))
  );
</script>

<svelte:head><title>{t('otp.pageTitle')}</title></svelte:head>

<div class="h-full overflow-y-auto no-sb p-8">
  <div class="max-w-4xl mx-auto">
    <h1 class="text-3xl font-black uppercase tracking-tight mb-2 text-black">{t('otp.title')}</h1>
    <p class="text-xs text-[#4B4B4B] uppercase tracking-widest mb-6 font-bold">
      {t('otp.subtitle')}
    </p>
    {#if message}<p class="nb-card p-2 text-sm text-black mb-3 font-bold">{message}</p>{/if}
    {#if loadError}<p class="nb-card p-2 text-sm text-black mb-3 font-bold">{loadError}</p>{/if}

    {#if otps.length === 0 && pendingProfiles.length === 0}
      <p class="nb-card p-3 text-sm text-black font-semibold">{t('otp.none')}</p>
    {:else}
      <div class="space-y-3">
        {#each otps as o}
          <div class="nb-card p-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p class="font-black text-black">{o.full_name || o.email}</p>
              <p class="text-xs text-[#4B4B4B] font-semibold">{o.email} · {t('otp.wants')} <strong>{o.requested_role}</strong>{o.hospital_name ? ` · ${o.hospital_name}` : ''}</p>
              {#if o.emailed_to?.length}
                <p class="text-[10px] uppercase tracking-widest text-black font-bold mt-1">
                  {o.email_sent ? t('otp.emailed') : t('otp.for')} {o.emailed_to.join(', ')}
                </p>
              {/if}
            </div>
            <div class="text-right nb-yellow p-2" style="border:3px solid #111;">
              <p class="text-[10px] uppercase tracking-widest text-black font-bold">OTP</p>
              <p class="text-3xl font-black tracking-[0.3em] text-black">{o.code}</p>
            </div>
          </div>
        {/each}
        {#each pendingProfiles as p}
          <div class="nb-card p-4">
            <p class="font-black text-black">{p.full_name || p.email}</p>
            <p class="text-xs text-[#4B4B4B] font-semibold">{p.email} · {t('otp.wants')} <strong>{p.requested_role}</strong> · {t('otp.fresh')}</p>
          </div>
        {/each}
      </div>
    {/if}

    <h2 class="nb-chip nb-blue mt-10 mb-3" style="color:#fff;">{t('otp.directory')}</h2>
    <div class="space-y-2">
      {#each profiles as p}
        <div class="text-xs flex justify-between nb-flat px-3 py-2 font-semibold">
          <span>{p.full_name || p.email}</span>
          <span class="uppercase font-black">{roleLabel(p.role)}{p.status === 'pending' ? ` · ${t('otp.pending')}` : ''}{p.ambulance_id ? ` · ${p.ambulance_id}` : ''}{p.hospital_name ? ` · ${p.hospital_name}` : ''}</span>
        </div>
      {/each}
    </div>
  </div>
</div>
