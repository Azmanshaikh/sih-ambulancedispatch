<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { auth, apiFetch, homeFor, refreshProfile } from '$lib/auth.svelte';
  import { t } from '$lib/i18n.svelte';
  import LanguageSettings from '$lib/components/LanguageSettings.svelte';

  type HospitalOption = { id: number; name: string };

  let picking = $state(false);
  let verifying = $state(false);
  let error = $state('');
  let otpSent = $state(
    Boolean(auth.profile?.requested_role && auth.profile?.status === 'pending' && (auth.profile?.requested_role !== 'staff' || auth.profile?.hospital_id))
  );
  let wanted = $state(auth.profile?.requested_role || '');
  let code = $state('');
  let otpHint = $state('');
  let pickHospital = $state(false);
  let hospitals = $state<HospitalOption[]>([]);
  let selectedHospital = $state<number | null>(auth.profile?.hospital_id ?? null);
  let selectedName = $state(auth.profile?.hospital_name || '');
  let loadingHospitals = $state(false);

  onMount(async () => {
    await loadHospitals();
    if (auth.profile?.requested_role === 'staff' && auth.profile?.status === 'pending' && !otpSent) {
      pickHospital = true;
    }
  });

  async function loadHospitals() {
    loadingHospitals = true;
    try {
      const res = await apiFetch('/hospitals/directory');
      if (res.ok) hospitals = await res.json();
    } catch {
      hospitals = [];
    } finally {
      loadingHospitals = false;
    }
  }

  function toggleHospital(id: number, name: string) {
    if (selectedHospital === id) {
      selectedHospital = null;
      selectedName = '';
      return;
    }
    selectedHospital = id;
    selectedName = name;
  }

  async function choose(role: 'patient' | 'driver' | 'staff') {
    error = '';
    if (role === 'staff') {
      pickHospital = true;
      otpSent = false;
      wanted = 'staff';
      await loadHospitals();
      return;
    }
    await submitRole(role);
  }

  async function submitRole(role: 'patient' | 'driver' | 'staff') {
    picking = true;
    error = '';
    try {
      const res = await apiFetch('/accounts/choose-role', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          role,
          hospital_id: role === 'staff' ? selectedHospital : null,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not save role');
      await refreshProfile();
      if (data.otp_sent) {
        otpSent = true;
        pickHospital = false;
        wanted = role;
        selectedName = data.hospital_name || selectedName;
        otpHint = data.message || 'OTP sent to head staff.';
        return;
      }
      goto(homeFor(auth.profile?.role), { replaceState: true });
    } catch (e: any) {
      error = e?.message || 'Failed';
    } finally {
      picking = false;
    }
  }

  async function requestStaffOtp() {
    if (selectedHospital == null) {
      error = t('choose.tickHospital');
      return;
    }
    await submitRole('staff');
  }

  async function verify() {
    verifying = true;
    error = '';
    try {
      const res = await apiFetch('/accounts/verify-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Invalid OTP');
      await refreshProfile();
      goto(homeFor(auth.profile?.role), { replaceState: true });
    } catch (e: any) {
      error = e?.message || 'Invalid OTP';
    } finally {
      verifying = false;
    }
  }

  function resetRole() {
    otpSent = false;
    pickHospital = false;
    code = '';
    wanted = '';
    error = '';
  }
</script>

<svelte:head><title>{t('choose.pageTitle')}</title></svelte:head>

<div class="h-full flex items-center justify-center p-6" style="position:relative;">
  <div style="position:absolute;top:16px;right:16px;z-index:20;">
    <LanguageSettings />
  </div>
  <div class="nb-card-lg" style="width:100%;max-width:520px;background:#fff;border:4px solid #111;padding:32px;">
    <div style="display:inline-flex;background:#FFD23F;border:3px solid #111;box-shadow:4px 4px 0 #111;padding:8px 12px;margin-bottom:16px;">
      <img src="/logo.png" alt="JEEVAN" style="height:56px;width:auto;max-width:100%;object-fit:contain;display:block;" />
    </div>
    <h1 style="margin:0 0 8px;font-size:26px;font-weight:900;text-transform:uppercase;">{t('choose.title')}</h1>
    <p style="margin:0 0 20px;font-size:13px;color:#4B4B4B;line-height:1.5;font-weight:500;">
      {t('choose.body', { email: auth.profile?.email || '' })}
    </p>

    {#if !otpSent && !pickHospital}
      <div style="display:flex;flex-direction:column;gap:12px;">
        <button class="btn btn-primary" style="width:100%;padding:16px;" disabled={picking} onclick={() => choose('patient')}>
          {t('choose.patient')}
        </button>
        <button class="btn btn-secondary" style="width:100%;padding:16px;" disabled={picking} onclick={() => choose('driver')}>
          {t('choose.driver')}
        </button>
        <button class="btn btn-blue" style="width:100%;padding:16px;" disabled={picking} onclick={() => choose('staff')}>
          {t('choose.staff')}
        </button>
      </div>
    {:else if pickHospital}
      <p style="font-size:13px;color:#111;margin:0 0 12px;font-weight:600;">
        {t('choose.pickHospital')}
      </p>
      {#if loadingHospitals}
        <p class="nb-card p-2" style="font-size:12px;font-weight:700;">{t('choose.loadingHospitals')}</p>
      {:else}
        <div style="display:flex;flex-direction:column;gap:8px;max-height:280px;overflow-y:auto;margin-bottom:14px;">
          {#each hospitals as h}
            <label
              class="nb-card"
              style="
                display:flex;align-items:center;gap:10px;padding:12px;cursor:pointer;
                background:{selectedHospital === h.id ? '#FFD23F' : '#fff'};
              "
            >
              <input
                type="checkbox"
                checked={selectedHospital === h.id}
                onchange={() => toggleHospital(h.id, h.name)}
                style="width:18px;height:18px;accent-color:#111;flex-shrink:0;"
              />
              <span style="font-size:13px;font-weight:800;">{h.name}</span>
            </label>
          {/each}
        </div>
      {/if}
      <button
        class="btn btn-primary"
        style="width:100%;padding:14px;"
        disabled={picking || selectedHospital == null}
        onclick={requestStaffOtp}
      >
        {picking ? t('choose.requestingOtp') : t('choose.requestOtp')}
      </button>
      <button class="btn btn-ghost" style="width:100%;margin-top:10px;" disabled={picking} onclick={resetRole}>
        {t('choose.differentRole')}
      </button>
    {:else}
      <p style="font-size:13px;color:#111;margin:0 0 12px;font-weight:600;">
        {t('choose.otpFor', { role: wanted })}
        {#if selectedName}{t('choose.atHospital', { name: selectedName })}{/if}
        {t('choose.otpSent')}
        {otpHint}
      </p>
      <input
        class="nb-input"
        bind:value={code}
        maxlength="6"
        inputmode="numeric"
        placeholder={t('choose.otpPlaceholder')}
        style="font-size:22px;letter-spacing:0.4em;text-align:center;margin-bottom:12px;"
      />
      <button class="btn btn-primary" style="width:100%;padding:14px;" disabled={verifying || code.length < 6} onclick={verify}>
        {verifying ? t('choose.checking') : t('choose.verify')}
      </button>
      <button class="btn btn-ghost" style="width:100%;margin-top:10px;" disabled={picking} onclick={resetRole}>
        {t('choose.differentRole')}
      </button>
    {/if}

    {#if error}
      <p class="nb-card p-2" style="color:#111;font-size:12px;margin:14px 0 0;font-weight:700;">{error}</p>
    {/if}
  </div>
</div>
