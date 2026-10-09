<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Sheet from '#lib/components/ui/sheet/index.js';
	import { Toaster } from '#lib/components/ui/sonner/index.js';
	import { Switch } from '#lib/components/ui/switch/index.js';
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import Menu from '@lucide/svelte/icons/menu';
	import Moon from '@lucide/svelte/icons/moon';
	import Settings from '@lucide/svelte/icons/settings';
	import { mode, setMode } from 'mode-watcher';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();

	let settingsOpen = $state(false);
	let view = $state<'menu' | 'settings'>('menu');

	// Always start on the menu when the drawer is opened.
	function openSettings() {
		view = 'menu';
		settingsOpen = true;
	}

	// Deterministic back targets, so back never bounces between screens.
	const backTargets: Record<string, string> = {
		'/template': '/',
		'/preview': '/template'
	};
	const backTarget = $derived(backTargets[page.url.pathname]);
	const showBack = $derived(backTarget !== undefined);

	const isDark = $derived(mode.current === 'dark');
</script>

<div class="app-shell min-h-dvh bg-muted text-foreground dark:bg-background">
	<header
		class="app-bar fixed inset-x-0 top-0 z-50 border-b border-border bg-background/90 backdrop-blur-md"
	>
		<div class="mx-auto flex h-14 w-full max-w-md items-center gap-1 px-3">
			{#if showBack}
				<Button
					variant="ghost"
					size="icon-lg"
					class="size-12"
					aria-label="Back"
					onclick={() => goto(backTarget ?? '/')}
				>
					<ChevronLeft class="size-7" />
				</Button>
			{:else}
				<Button
					variant="ghost"
					size="icon-lg"
					class="size-11"
					aria-label="Open settings"
					onclick={openSettings}
				>
					<Menu />
				</Button>
				<a href="/" aria-label="Home" class="flex h-11 items-center">
					<img src="/logo.svg" alt="Logo" class="h-8 w-auto" />
				</a>
			{/if}
		</div>
	</header>

	<main class="app-content mx-auto w-full max-w-md px-3">
		{@render children()}
	</main>

	<Toaster theme={isDark ? 'dark' : 'light'} position="top-center" />

	<Sheet.Root bind:open={settingsOpen}>
		<Sheet.Content side="left" class="w-72 gap-0 p-0">
			{#if view === 'menu'}
				<Sheet.Header class="border-b border-border px-4 py-4">
					<Sheet.Title>Menu</Sheet.Title>
					<Sheet.Description class="sr-only">App menus</Sheet.Description>
				</Sheet.Header>

				<nav class="space-y-1 p-2">
					<button
						type="button"
						class="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm font-medium transition-colors hover:bg-muted"
						onclick={() => (view = 'settings')}
					>
						<Settings class="size-5 text-muted-foreground" />
						Settings
						<ChevronRight class="ml-auto size-4 text-muted-foreground" />
					</button>
				</nav>
			{:else}
				<div class="flex items-center gap-1 border-b border-border px-2 py-2">
					<Button
						variant="ghost"
						size="icon-lg"
						class="size-10"
						aria-label="Back to menu"
						onclick={() => (view = 'menu')}
					>
						<ChevronLeft class="size-5" />
					</Button>
					<Sheet.Title class="text-base font-semibold">Settings</Sheet.Title>
					<Sheet.Description class="sr-only">App preferences</Sheet.Description>
				</div>

				<div class="px-4 py-4">
					<label
						class="flex items-center justify-between gap-3 rounded-xl border border-border/60 bg-card px-3 py-3"
					>
						<span class="flex items-center gap-2 text-sm font-medium">
							<Moon class="size-4 text-muted-foreground" />
							Dark mode
						</span>
						<Switch
							checked={isDark}
							onCheckedChange={(checked) => setMode(checked ? 'dark' : 'light')}
							aria-label="Toggle dark mode"
						/>
					</label>
				</div>
			{/if}
		</Sheet.Content>
	</Sheet.Root>
</div>

<style>
	.app-shell {
		--gutter: 0.75rem;
		--bar-h: 3.5rem;
		--action-h: 3.5rem;
		--safe-top: env(safe-area-inset-top, 0px);
		--safe-bottom: env(safe-area-inset-bottom, 0px);
	}

	.app-bar {
		padding-top: var(--safe-top);
	}

	.app-content {
		padding-top: calc(var(--bar-h) + var(--safe-top) + var(--gutter));
		padding-bottom: calc(var(--action-h) + 0.5rem + max(var(--gutter), var(--safe-bottom)) + var(--gutter));
	}
</style>
