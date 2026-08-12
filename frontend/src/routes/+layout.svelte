<script lang="ts">
  import '../app.css';
  import TopNav from '$lib/components/TopNav.svelte';
  import HospitalLoginModal from '$lib/components/HospitalLoginModal.svelte';
  import WelcomeModal from '$lib/components/WelcomeModal.svelte';
  import { onMount } from 'svelte';
  import type { Snippet } from 'svelte';

  interface Props { children: Snippet; }
  let { children }: Props = $props();

  let isLoginModalOpen = $state(false);
  let isWelcomeModalOpen = $state(false);
  let gpsStatus = $state('Acquiring GPS…');

  onMount(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => gpsStatus = `${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`,
        () => gpsStatus = 'GPS denied — using default'
      );
    } else {
      gpsStatus = 'GPS not supported';
    }
  });

  function handleLoginSuccess() {
    isLoginModalOpen = false;
    isWelcomeModalOpen = true;
  }
</script>

<TopNav
  onHospitalLoginClick={() => (isLoginModalOpen = true)}
  {gpsStatus}
/>

<HospitalLoginModal
  isOpen={isLoginModalOpen}
  onClose={() => (isLoginModalOpen = false)}
  onLoginSuccess={handleLoginSuccess}
/>

<WelcomeModal
  isOpen={isWelcomeModalOpen}
  onClose={() => (isWelcomeModalOpen = false)}
/>

<main style="padding-top: 88px; flex: 1; display: flex; flex-direction: column; overflow: hidden; width: 100%; height: 100vh;">
  <div class="flex-1 overflow-hidden relative h-full">
    {@render children()}
  </div>
</main>
