<script lang="ts">
  import { goto } from '$app/navigation';
  import { auth, apiFetch, homeFor, refreshProfile } from '$lib/auth.svelte';

  let picking = $state(false);
  let verifying = $state(false);
  let error = $state('');
  let otpSent = $state(Boolean(auth.profile?.requested_role && auth.profile?.status === 'pending'));
  let wanted = $state(auth.profile?.requested_role || '');
  let code = $state('');

  async function choose(role: 'patient' | 'driver' | 'staff') {
    picking = true;
    error = '';
    try {
      const res = await apiFetch('/accounts/choose-role', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not save role');
      await refreshProfile();
      if (data.otp_sent) {
        otpSent = true;
        wanted = role;
        return;
      }
      goto(homeFor(auth.profile?.role), { replaceState: true });
    } catch (e: any) {
      error = e?.message || 'Failed';
    } finally {
      picking = false;
    }
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
</script>

<svelte:head><title>JEEVAN — Choose role</title></svelte:head>

<div class="h-full flex items-center justify-center p-6" style="background:#F5F5F5;">
  <div style="width:100%;max-width:460px;background:#fff;border:2px solid #DC2626;padding:32px;">
    <img src="/logo.png" alt="JEEVAN" style="height:72px;width:auto;max-width:100%;object-fit:contain;margin:0 0 16px;display:block;" />
    <h1 style="margin:0 0 8px;font-size:22px;">Who are you?</h1>
    <p style="margin:0 0 20px;font-size:13px;color:#6B6B6B;line-height:1.5;">
      Signed in as <strong>{auth.profile?.email}</strong>. Patients enter immediately. Drivers and new staff must get an OTP from main staff.
    </p>

    {#if !otpSent}
      <div style="display:flex;flex-direction:column;gap:10px;">
        <button class="btn btn-primary" style="width:100%;padding:14px;" disabled={picking} onclick={() => choose('patient')}>
          Patient — no approval
        </button>
        <button class="btn btn-ghost" style="width:100%;padding:14px;border:2px solid #DC2626;" disabled={picking} onclick={() => choose('driver')}>
          Driver — OTP from staff
        </button>
        <button class="btn btn-ghost" style="width:100%;padding:14px;border:2px solid #DC2626;" disabled={picking} onclick={() => choose('staff')}>
          Staff — OTP from main staff
        </button>
      </div>
    {:else}
      <p style="font-size:13px;color:#1A1A1A;margin:0 0 12px;">
        OTP for <strong>{wanted}</strong> was sent to staff. Ask them for the 6-digit code.
      </p>
      <input
        bind:value={code}
        maxlength="6"
        inputmode="numeric"
        placeholder="6-digit OTP"
        style="width:100%;border:2px solid #E0E0E0;padding:12px;font-size:20px;letter-spacing:0.4em;text-align:center;margin-bottom:12px;"
      />
      <button class="btn btn-primary" style="width:100%;padding:12px;" disabled={verifying || code.length < 6} onclick={verify}>
        {verifying ? 'Checking…' : 'Verify OTP'}
      </button>
      <button class="btn btn-ghost" style="width:100%;margin-top:8px;" disabled={picking} onclick={() => { otpSent = false; code = ''; }}>
        Choose a different role
      </button>
    {/if}

    {#if error}
      <p style="color:#DC2626;font-size:12px;margin:12px 0 0;">{error}</p>
    {/if}
  </div>
</div>
