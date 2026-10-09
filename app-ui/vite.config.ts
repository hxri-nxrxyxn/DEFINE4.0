import tailwindcss from '@tailwindcss/vite';
import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		tailwindcss(),
		sveltekit({
			compilerOptions: {
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},
			adapter: adapter({
				pages: 'build',
				assets: 'build',
				fallback: 'index.html',
				precompress: false,
				strict: false
			})
		})
	],
	optimizeDeps: {
		include: [
			'bits-ui',
			'svelte-sonner',
			'mode-watcher',
			'tailwind-variants',
			'cn',
			'layerchart',
			'd3-scale',
			'd3-shape'
		]
	},
	server: {
		host: true,
		port: 5173,
		strictPort: true,
		allowedHosts: true,
		warmup: {
			clientFiles: [
				'./src/routes/(app)/+layout.svelte',
				'./src/routes/(app)/+page.svelte'
			]
		}
	}
});
