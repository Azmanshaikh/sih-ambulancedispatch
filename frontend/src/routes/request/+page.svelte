<script lang="ts">
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import { apiFetch } from '$lib/auth.svelte';
  import LocationPicker from '$lib/components/LocationPicker.svelte';
  import { lookupAddress, lookupCoords } from '$lib/geocode';
  import { t } from '$lib/i18n.svelte';

  const BMSIT = {
    name: 'BMSIT College, Avalahalli, Yelahanka',
    lat: 13.1344,
    lng: 77.5693,
  };

  let description = $state('');
  let whatsHappening = $state('');
  let narrative = $state('');
  let age = $state('adult');
  let reportFile = $state<File | null>(null);
  let analysisResult = $state('');
  let analysisSaved = $state(false);
  let savedReports = $state<any[]>([]);
  let isAnalyzing = $state(false);
  let dispatching = $state(false);
  let cardiac = $state(false);
  let diabetes = $state(false);
  let epilepsy = $state(false);
  let pregnant = $state(false);
  let emergencyCategory = $state('general_medical');
  let accessibilityNeed = $state(false);
  let address = $state(BMSIT.name);
  let pinLat = $state(BMSIT.lat);
  let pinLng = $state(BMSIT.lng);
  let locating = $state(false);
  let locationError = $state('');

  type QuickPreset = 'cardiac_arrest' | 'road_accident' | 'unconsciousness';
  let selectedPreset = $state<QuickPreset | null>(null);

  const QUICK_PRESETS: {
    id: QuickPreset;
    label: string;
    icon: string;
    category: string;
    summary: string;
    cardiac?: boolean;
    epilepsy?: boolean;
  }[] = [
    {
      id: 'cardiac_arrest',
      label: 'Cardiac arrest',
      icon: 'favorite',
      category: 'cardiac',
      summary: 'Suspected cardiac arrest — patient unresponsive, CPR may be in progress.',
      cardiac: true,
    },
    {
      id: 'road_accident',
      label: 'Road accident',
      icon: 'car_crash',
      category: 'trauma',
      summary: 'Road traffic accident — trauma injuries reported at scene.',
    },
    {
      id: 'unconsciousness',
      label: 'Unconsciousness',
      icon: 'bedtime',
      category: 'neurological',
      summary: 'Patient is unconscious or not responding — cause unknown.',
      epilepsy: false,
    },
  ];

  function applyPreset(id: QuickPreset) {
    selectedPreset = id;
    const preset = QUICK_PRESETS.find((p) => p.id === id);
    if (!preset) return;
    emergencyCategory = preset.category;
    cardiac = Boolean(preset.cardiac);
    epilepsy = Boolean(preset.epilepsy);
    if (!whatsHappening.trim()) whatsHappening = preset.summary;
  }

  async function loadSavedReports() {
    try {
      const res = await apiFetch('/ai/reports');
      if (!res.ok) return;
      const data = await res.json();
      savedReports = data.reports || [];
    } catch {
      /* ignore */
    }
  }

  async function geocodeAddress() {
    const q = address.trim();
    if (!q) return;
    locating = true;
    locationError = '';
    try {
      const hit = await lookupAddress(q);
      if (!hit) {
        locationError = 'Address not found. Pin it on the map instead.';
        return;
      }
      pinLat = hit.lat;
      pinLng = hit.lng;
      if (hit.address) address = hit.address;
    } catch {
      locationError = 'Could not look up that address. Pin it on the map instead.';
    } finally {
      locating = false;
    }
  }

  async function onPin(lat: number, lng: number) {
    pinLat = lat;
    pinLng = lng;
    locationError = '';
    try {
      const hit = await lookupCoords(lat, lng);
      address = hit.address;
    } catch {
      address = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
    }
  }

  async function handleAnalyzeReport() {
    if (!description && !reportFile) {
      alert('Please provide a description or upload a report.');
      return;
    }
    isAnalyzing = true;
    analysisResult = '';
    analysisSaved = false;
    const formData = new FormData();
    if (description) formData.append('text', description);
    if (reportFile) formData.append('image', reportFile);
    try {
      const res = await apiFetch('/ai/analyze-report', { method: 'POST', body: formData });
      const data = await res.json();
      if (data.status === 'success') {
        analysisResult = data.analysis;
        analysisSaved = Boolean(data.saved);
        await loadSavedReports();
      } else {
        analysisResult = `Error: ${data.detail || data.message}`;
      }
    } catch (err) {
      console.error(err);
      analysisResult = 'Failed to connect to the analysis service.';
    } finally {
      isAnalyzing = false;
    }
  }

  async function dispatchNow() {
    dispatching = true;
    try {
      const notes = [whatsHappening, description, narrative, analysisResult ? `AI analysis:\n${analysisResult}` : '']
        .filter(Boolean)
        .join('\n\n');
      const res = await apiFetch('/tracking/dispatch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          incident_lat: pinLat,
          incident_lng: pinLng,
          address: address.trim() || BMSIT.name,
          notes,
          analysis: analysisResult,
          cardiac,
          diabetes,
          epilepsy,
          pregnant,
          emergency_category: emergencyCategory,
          age_group: age,
          accessibility_need: accessibilityNeed,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        alert(data.detail || 'Dispatch failed');
        return;
      }
      goto('/');
    } finally {
      dispatching = false;
    }
  }

  onMount(() => {
    loadSavedReports();
  });
</script>

<svelte:head><title>{t('request.pageTitle')}</title></svelte:head>

<div class="request-page">
  <div class="request-inner">

    <div style="margin-bottom: 32px; padding-bottom: 20px; border-bottom: 1px solid var(--clr-border);">
      <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 6px;">
        <div style="width: 4px; height: 36px; background: var(--clr-primary); border-radius: 4px;"></div>
        <h1 style="margin: 0; font-size: 24px; font-weight: 800; color: var(--clr-ink);">{t('request.title')}</h1>
      </div>
      <p style="margin: 0 0 12px 16px; font-size: 11px; font-weight: 600; color: var(--clr-muted); text-transform: uppercase; letter-spacing: 0.08em;">{t('request.subtitle')}</p>
      <div class="nb-chip chip-info" style="margin-left: 16px;">
        🛰️ 📍 {address}
      </div>
    </div>

    <section class="situation-section nb-card">
      <h2 class="section-title">{t('request.whatsHappening')}</h2>
      <p class="section-hint">{t('request.whatsHappeningHint')}</p>
      <textarea
        class="nb-input situation-text"
        placeholder={t('request.whatsHappeningPlaceholder')}
        bind:value={whatsHappening}
      ></textarea>

      <p class="preset-label">{t('request.quickEmergency')}</p>
      <div class="preset-grid">
        {#each QUICK_PRESETS as preset}
          <button
            type="button"
            class="preset-card"
            class:preset-card--active={selectedPreset === preset.id}
            onclick={() => applyPreset(preset.id)}
          >
            <span class="material-symbols-outlined preset-icon">{preset.icon}</span>
            <span class="preset-name">{preset.label}</span>
          </button>
        {/each}
      </div>
    </section>

    <div style="margin-bottom: 28px;">
      <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <div style="width: 3px; height: 16px; background: #DC2626;"></div>
        <h3 style="margin: 0; font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.25em; color: #DC2626;">{t('request.pickup')}</h3>
      </div>
      <div style="background:#fff;border:3px solid #111;padding:16px;display:flex;flex-direction:column;gap:12px;">
        <label style="font-size:10px;font-weight:700;color:#6B6B6B;text-transform:uppercase;letter-spacing:0.2em;">{t('request.addressHint')}</label>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <input
            bind:value={address}
            onkeydown={(e) => e.key === 'Enter' && geocodeAddress()}
            placeholder={t('request.addressPlaceholder')}
            style="flex:1;min-width:220px;background:#F5F5F5;border:3px solid #111;padding:10px 12px;font-size:13px;color:#1A1A1A;outline:none;font-family:Inter,sans-serif;"
          />
          <button type="button" class="btn btn-secondary" style="padding:10px 14px;" disabled={locating} onclick={geocodeAddress}>
            {locating ? t('request.finding') : t('request.findAddress')}
          </button>
        </div>
        {#if locationError}
          <p style="margin:0;font-size:12px;font-weight:700;color:#DC2626;">{locationError}</p>
        {/if}
        <LocationPicker lat={pinLat} lng={pinLng} {onPin} />
        <p style="margin:0;font-size:11px;font-weight:700;color:#4B4B4B;">
          {pinLat.toFixed(5)}, {pinLng.toFixed(5)}
        </p>
      </div>
    </div>

    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 32px;">

      <div style="display: flex; flex-direction: column; gap: 20px;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <div style="width: 3px; height: 16px; background: #1A1A1A;"></div>
          <h3 style="margin: 0; font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.25em; color: #1A1A1A;">{t('request.incident')}</h3>
        </div>

        <textarea
          style="width:100%;box-sizing:border-box;height:128px;background:#FFFFFF;border:3px solid #111;border-radius:0;padding:14px;font-size:13px;color:#1A1A1A;font-family:'Inter',sans-serif;outline:none;resize:vertical;"
          placeholder={t('request.incidentPlaceholder')}
          bind:value={description}
        ></textarea>

        <div>
          <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
            <div style="width: 3px; height: 16px; background: #DC2626;"></div>
            <h3 style="margin: 0; font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.25em; color: #DC2626;">{t('request.triage')}</h3>
          </div>

          <div style="background: #FFFFFF; border: 3px solid #111; padding: 16px; display: flex; flex-direction: column; gap: 12px;">
            <label style="font-size: 10px; font-weight: 700; color: #6B6B6B; text-transform: uppercase; letter-spacing: 0.2em; display: block;">{t('request.upload')}</label>
            <input
              type="file"
              accept="image/*"
              onchange={(e) => reportFile = (e.target as HTMLInputElement).files?.[0] ?? null}
              style="font-size: 11px; color: #6B6B6B; width: 100%; cursor: pointer;"
            />
            <button
              onclick={handleAnalyzeReport}
              disabled={isAnalyzing}
              class="btn btn-secondary"
              style="width: 100%; padding: 10px;"
            >
              {isAnalyzing ? t('request.analyzing') : t('request.analyze')}
            </button>
          </div>

          {#if analysisResult}
            <div style="background: #FFFFFF; border: 3px solid #111; border-left-width: 8px; box-shadow: 4px 4px 0 #111; padding: 16px; margin-top: 12px; max-height: 200px; overflow-y: auto;">
              <h4 style="margin: 0 0 8px; font-size: 10px; font-weight: 700; color: #DC2626; text-transform: uppercase; letter-spacing: 0.2em;">{t('request.aiResult')}</h4>
              {#if analysisSaved}
                <p style="margin:0 0 8px;font-size:11px;font-weight:800;color:#15803d;">{t('request.savedAccount')}</p>
              {/if}
              <p style="margin: 0; font-size: 13px; color: #1A1A1A; white-space: pre-wrap; line-height: 1.6;">{analysisResult}</p>
            </div>
          {/if}

          {#if savedReports.length}
            <div style="background:#fff;border:3px solid #111;padding:12px;margin-top:12px;">
              <p style="margin:0 0 8px;font-size:10px;font-weight:900;letter-spacing:0.2em;text-transform:uppercase;color:#4B4B4B;">{t('request.savedOnAccount')}</p>
              {#each savedReports.slice(0, 3) as r}
                <button
                  type="button"
                  class="block w-full text-left"
                  style="border:2px solid #111;padding:8px;margin-bottom:6px;background:#F5F5F5;cursor:pointer;"
                  onclick={() => { analysisResult = r.analysis; if (r.input_text) description = r.input_text; }}
                >
                  <p style="margin:0;font-size:10px;font-weight:800;color:#4B4B4B;">{(r.created_at || '').slice(0, 16)} {r.image_name ? `· ${r.image_name}` : ''}</p>
                  <p style="margin:4px 0 0;font-size:12px;color:#111;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">{r.analysis}</p>
                </button>
              {/each}
            </div>
          {/if}
        </div>
      </div>

      <div style="display: flex; flex-direction: column; gap: 20px;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <div style="width: 3px; height: 16px; background: #DC2626;"></div>
          <h3 style="margin: 0; font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.25em; color: #DC2626;">{t('request.context')}</h3>
        </div>

        <div style="background: #FFFFFF; border: 3px solid #111; padding: 24px; display: flex; flex-direction: column; gap: 16px;">
          <div>
            <label style="display: block; font-size: 10px; font-weight: 700; color: #6B6B6B; text-transform: uppercase; letter-spacing: 0.2em; margin-bottom: 8px;">{t('request.narrative')}</label>
            <textarea
              style="width:100%;box-sizing:border-box;background:#F5F5F5;border:3px solid #111;border-radius:0;padding:12px;color:#1A1A1A;font-family:'Inter',sans-serif;font-size:13px;min-height:90px;resize:none;outline:none;"
              placeholder={t('request.narrativePlaceholder')}
              bind:value={narrative}
            ></textarea>
          </div>

          <div>
            <label for="age-select" style="display: block; font-size: 10px; font-weight: 700; color: #6B6B6B; text-transform: uppercase; letter-spacing: 0.2em; margin-bottom: 6px;">{t('request.age')}</label>
            <select id="age-select" bind:value={age} style="width: 100%; background: #F5F5F5; border: 3px solid #111; border-radius: 0; padding: 8px 10px; font-size: 13px; color: #1A1A1A; outline: none; font-family: 'Inter', sans-serif;">
              <option value="infant">{t('request.infant')}</option>
              <option value="child">{t('request.child')}</option>
              <option value="teen">{t('request.teen')}</option>
              <option value="adult">{t('request.adult')}</option>
              <option value="elderly">{t('request.elderly')}</option>
            </select>
          </div>

          <div>
            <label for="emergency-category" style="display: block; font-size: 10px; font-weight: 700; color: #6B6B6B; text-transform: uppercase; letter-spacing: 0.2em; margin-bottom: 6px;">Emergency type</label>
            <select id="emergency-category" bind:value={emergencyCategory} style="width: 100%; background: #F5F5F5; border: 3px solid #111; border-radius: 0; padding: 8px 10px; font-size: 13px; color: #1A1A1A; outline: none; font-family: 'Inter', sans-serif;">
              <option value="general_medical">General medical</option>
              <option value="cardiac">Cardiac / chest pain</option>
              <option value="respiratory">Breathing emergency</option>
              <option value="neurological">Stroke / seizure</option>
              <option value="trauma">Trauma / accident</option>
              <option value="obstetric">Pregnancy / labour</option>
              <option value="pediatric">Infant / child emergency</option>
              <option value="bariatric_accessible">Mobility / bariatric transport</option>
            </select>
            <p style="margin:6px 0 0;font-size:10px;color:#4B4B4B;font-weight:600;">We send the nearest ambulance equipped for this emergency.</p>
          </div>

          <label style="display: flex; align-items: center; gap: 8px; font-size: 12px; color: #1A1A1A; cursor: pointer; font-weight: 600;"><input type="checkbox" bind:checked={accessibilityNeed} style="accent-color: #DC2626;" /> Mobility, wheelchair, or bariatric accommodation needed</label>

          <div style="padding-top: 12px; border-top: 2px solid #E0E0E0;">
            <p style="font-size: 10px; font-weight: 700; color: #6B6B6B; text-transform: uppercase; letter-spacing: 0.2em; margin: 0 0 10px;">{t('request.history')}</p>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
              <label style="display: flex; align-items: center; gap: 8px; font-size: 12px; color: #1A1A1A; cursor: pointer; font-weight: 600;"><input type="checkbox" bind:checked={cardiac} style="accent-color: #DC2626;" /> {t('request.cardiac')}</label>
              <label style="display: flex; align-items: center; gap: 8px; font-size: 12px; color: #1A1A1A; cursor: pointer; font-weight: 600;"><input type="checkbox" bind:checked={diabetes} style="accent-color: #DC2626;" /> {t('patient.diabetes')}</label>
              <label style="display: flex; align-items: center; gap: 8px; font-size: 12px; color: #1A1A1A; cursor: pointer; font-weight: 600;"><input type="checkbox" bind:checked={epilepsy} style="accent-color: #DC2626;" /> {t('patient.epilepsy')}</label>
              <label style="display: flex; align-items: center; gap: 8px; font-size: 12px; color: #1A1A1A; cursor: pointer; font-weight: 600;"><input type="checkbox" bind:checked={pregnant} style="accent-color: #DC2626;" /> {t('patient.pregnant')}</label>
            </div>
          </div>
        </div>

        <div style="display: flex; gap: 12px; padding-top: 4px;">
          <button onclick={() => goto('/')} class="btn btn-ghost" style="flex: 1; padding: 14px;">
            {t('request.cancel')}
          </button>
          <button
            disabled={dispatching}
            onclick={dispatchNow}
            class="btn btn-success"
            style="flex: 2; padding: 14px; font-size: 12px; letter-spacing: 0.2em;"
          >
            {dispatching ? t('request.assigning') : t('request.assign')}
          </button>
        </div>
      </div>

    </div>
  </div>
</div>

<style>
  .request-page {
    height: 100%;
    min-height: 0;
    overflow-y: auto;
    overflow-x: hidden;
    -webkit-overflow-scrolling: touch;
  }
  .request-inner {
    padding: 32px 32px 48px;
    max-width: 1100px;
    margin: 0 auto;
    width: 100%;
    box-sizing: border-box;
  }
  .situation-section {
    padding: 20px;
    margin-bottom: 28px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .section-title {
    margin: 0;
    font-size: 13px;
    font-weight: 700;
    color: var(--clr-ink);
  }
  .section-hint {
    margin: 0;
    font-size: 12px;
    color: var(--clr-muted);
    line-height: 1.45;
  }
  .situation-text {
    min-height: 88px;
    resize: vertical;
    font-size: 14px;
    line-height: 1.5;
  }
  .preset-label {
    margin: 8px 0 0;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--clr-muted);
  }
  .preset-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
  }
  .preset-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 16px 10px;
    border: 1px solid var(--clr-border);
    border-radius: var(--radius-md);
    background: var(--clr-surface2);
    cursor: pointer;
    transition: border-color 0.15s, background 0.15s, box-shadow 0.15s;
    text-align: center;
  }
  .preset-card:hover {
    border-color: var(--clr-primary);
    background: #eff6ff;
  }
  .preset-card--active {
    border-color: var(--clr-primary);
    background: #eff6ff;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.2);
  }
  .preset-icon {
    font-size: 28px;
    color: var(--clr-primary);
  }
  .preset-card--active .preset-icon {
    color: var(--clr-danger);
  }
  .preset-name {
    font-size: 12px;
    font-weight: 700;
    color: var(--clr-ink);
    line-height: 1.3;
  }
  @media (max-width: 640px) {
    .preset-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
