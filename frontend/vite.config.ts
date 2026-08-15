import { fileURLToPath } from 'node:url';
import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	envDir: fileURLToPath(new URL('..', import.meta.url)),
	plugins: [tailwindcss(), sveltekit()],
});
