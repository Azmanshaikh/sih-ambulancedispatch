<script lang="ts">
  import { goto } from '$app/navigation';
  import { apiFetch } from '$lib/auth.svelte';

  let description = $state('');
  let narrative = $state('');
  let age = $state('adult');
  let reportFile = $state<File | null>(null);
  let analysisResult = $state('');
  let isAnalyzing = $state(false);
  let dispatching = $state(false);
  let cardiac = $state(false);
  let diabetes = $state(false);
  let epilepsy = $state(false);
  let pregnant = $state(false);

  async function handleAnalyzeReport() {
    if (!description && !reportFile) {
      alert('Please provide a description or upload a report.');
      return;
    }
    isAnalyzing = true;
    analysisResult = '';
    const formData = new FormData();
    if (description) formData.append('text', description);
    if (reportFile) formData.append('image', reportFile);
    try {
      const res = await apiFetch('/ai/analyze-report', { method: 'POST', body: formData });
      const data = await res.json();
      analysisResult = data.status === 'success' ? data.analysis : `Error: ${data.detail || data.message}`;
    } catch (err) {
      console.error(err);
      analysisResult = 'Failed to connect to the analysis service.';
    } finally {
      isAnalyzing = false;
    }
  }
</script>

<svelte:head><title>JEEVAN — New Request</title></svelte:head>

<div style="flex: 1; overflow-y: auto;">
  <div style="padding: 32px; max-width: 1100px; margin: 0 auto; width: 100%; box-sizing: border-box;">

    <!-- Page Header -->
    <div style="margin-bottom: 32px; padding-bottom: 20px; border-bottom: 4px solid #111;">
      <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 6px;">
        <div style="width: 10px; height: 40px; background: #FF2D2D; border: 3px solid #111;"></div>
        <h1 style="margin: 0; font-family: 'Orbitron', sans-serif; font-size: 26px; font-weight: 900; color: #111; text-transform: uppercase; letter-spacing: 0.05em;">New Dispatch Request</h1>
      </div>
      <p style="margin: 0 0 12px 22px; font-size: 10px; font-weight: 700; color: #4B4B4B; text-transform: uppercase; letter-spacing: 0.3em;">AI-Powered Triage &amp; Fleet Assignment</p>
      <div class="nb-chip nb-yellow" style="margin-left: 22px;">
        🛰️ 📍 BMSIT College, Avalahalli, Yelahanka
      </div>
    </div>

    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 32px;">

      <!-- LEFT: Incident Details + AI -->
      <div style="display: flex; flex-direction: column; gap: 20px;">

        <!-- Section header -->
        <div style="display: flex; align-items: center; gap: 8px;">
          <div style="width: 3px; height: 16px; background: #1A1A1A;"></div>
          <h3 style="margin: 0; font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.25em; color: #1A1A1A;">Incident Details</h3>
        </div>

        <textarea
          style="
            width: 100%; box-sizing: border-box;
            height: 128px;
            background: #FFFFFF;
            border: 3px solid #111;
            border-radius: 0;
            padding: 14px;
            font-size: 13px;
            color: #1A1A1A;
            font-family: 'Inter', sans-serif;
            outline: none;
            resize: vertical;
            transition: border-color 0.15s;
          "
          placeholder="Describe the emergency in detail (e.g., 'Severe bleeding from left foot after fall')"
          bind:value={description}
          onfocus={(e) => (e.target as HTMLTextAreaElement).style.borderColor = '#DC2626'}
          onblur={(e) => (e.target as HTMLTextAreaElement).style.borderColor = '#111'}
        ></textarea>

        <!-- AI Analysis Section -->
        <div>
          <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
            <div style="width: 3px; height: 16px; background: #DC2626;"></div>
            <h3 style="margin: 0; font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.25em; color: #DC2626;">Quick Triage &amp; AI Analysis</h3>
          </div>

          <div style="background: #FFFFFF; border: 3px solid #111; padding: 16px; display: flex; flex-direction: column; gap: 12px;">
            <label style="font-size: 10px; font-weight: 700; color: #6B6B6B; text-transform: uppercase; letter-spacing: 0.2em; display: block;">Upload Medical Report (Image)</label>
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
              {isAnalyzing ? '⏳ Analyzing with NVIDIA AI...' : '🔍 Analyze Report & Description'}
            </button>
          </div>

          {#if analysisResult}
            <div style="background: #FFFFFF; border: 3px solid #111; border-left-width: 8px; box-shadow: 4px 4px 0 #111; padding: 16px; margin-top: 12px; max-height: 200px; overflow-y: auto;">
              <h4 style="margin: 0 0 8px; font-size: 10px; font-weight: 700; color: #DC2626; text-transform: uppercase; letter-spacing: 0.2em;">AI Assessment Result</h4>
              <p style="margin: 0; font-size: 13px; color: #1A1A1A; white-space: pre-wrap; line-height: 1.6;">{analysisResult}</p>
            </div>
          {/if}
        </div>
      </div>

      <!-- RIGHT: Context -->
      <div style="display: flex; flex-direction: column; gap: 20px;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <div style="width: 3px; height: 16px; background: #DC2626;"></div>
          <h3 style="margin: 0; font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.25em; color: #DC2626;">Incident Context</h3>
        </div>

        <div style="background: #FFFFFF; border: 3px solid #111; padding: 24px; display: flex; flex-direction: column; gap: 16px;">
          <div>
            <label style="display: block; font-size: 10px; font-weight: 700; color: #6B6B6B; text-transform: uppercase; letter-spacing: 0.2em; margin-bottom: 8px;">Scene Narrative</label>
            <textarea
              style="
                width: 100%; box-sizing: border-box;
                background: #F5F5F5;
                border: 3px solid #111;
                border-radius: 0;
                padding: 12px;
                color: #1A1A1A;
                font-family: 'Inter', sans-serif;
                font-size: 13px;
                min-height: 90px;
                resize: none;
                outline: none;
                transition: border-color 0.15s;
              "
              placeholder="Describe the situation…"
              bind:value={narrative}
              onfocus={(e) => (e.target as HTMLTextAreaElement).style.borderColor = '#DC2626'}
              onblur={(e) => (e.target as HTMLTextAreaElement).style.borderColor = '#111'}
            ></textarea>
          </div>

          <div>
            <label for="age-select" style="display: block; font-size: 10px; font-weight: 700; color: #6B6B6B; text-transform: uppercase; letter-spacing: 0.2em; margin-bottom: 6px;">Age Group</label>
            <select id="age-select" bind:value={age} style="width: 100%; background: #F5F5F5; border: 3px solid #111; border-radius: 0; padding: 8px 10px; font-size: 13px; color: #1A1A1A; outline: none; font-family: 'Inter', sans-serif;">
              <option value="infant">Infant (0-1)</option>
              <option value="child">Child (2-12)</option>
              <option value="teen">Teen (13-17)</option>
              <option value="adult">Adult (18-60)</option>
              <option value="elderly">Elderly (60+)</option>
            </select>
          </div>

          <div style="padding-top: 12px; border-top: 2px solid #E0E0E0;">
            <p style="font-size: 10px; font-weight: 700; color: #6B6B6B; text-transform: uppercase; letter-spacing: 0.2em; margin: 0 0 10px;">Medical History</p>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
              <label style="display: flex; align-items: center; gap: 8px; font-size: 12px; color: #1A1A1A; cursor: pointer; font-weight: 600;"><input type="checkbox" bind:checked={cardiac} style="accent-color: #DC2626;" /> Cardiac History</label>
              <label style="display: flex; align-items: center; gap: 8px; font-size: 12px; color: #1A1A1A; cursor: pointer; font-weight: 600;"><input type="checkbox" bind:checked={diabetes} style="accent-color: #DC2626;" /> Diabetes</label>
              <label style="display: flex; align-items: center; gap: 8px; font-size: 12px; color: #1A1A1A; cursor: pointer; font-weight: 600;"><input type="checkbox" bind:checked={epilepsy} style="accent-color: #DC2626;" /> Epilepsy</label>
              <label style="display: flex; align-items: center; gap: 8px; font-size: 12px; color: #1A1A1A; cursor: pointer; font-weight: 600;"><input type="checkbox" bind:checked={pregnant} style="accent-color: #DC2626;" /> Pregnant</label>
            </div>
          </div>
        </div>

        <!-- Action Buttons -->
        <div style="display: flex; gap: 12px; padding-top: 4px;">
          <button onclick={() => goto('/')} class="btn btn-ghost" style="flex: 1; padding: 14px;">
            Cancel
          </button>
          <button
            disabled={dispatching}
            onclick={async () => {
              dispatching = true;
              try {
                await apiFetch('/tracking/dispatch', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({
                    incident_lat: 13.1344,
                    incident_lng: 77.5693,
                    address: 'BMSIT College, Avalahalli, Yelahanka',
                    notes: [description, narrative].filter(Boolean).join('\n'),
                    cardiac,
                    diabetes,
                    epilepsy,
                    pregnant,
                  }),
                });
              } finally {
                dispatching = false;
                goto('/');
              }
            }}
            class="btn btn-primary"
            style="flex: 2; padding: 14px; font-size: 12px; letter-spacing: 0.2em; box-shadow: 0 6px 20px rgba(220,38,38,0.35);"
          >
            {dispatching ? 'Assigning fastest unit…' : 'Auto-assign fastest unit'}
          </button>
        </div>
      </div>

    </div>
  </div>
</div>
