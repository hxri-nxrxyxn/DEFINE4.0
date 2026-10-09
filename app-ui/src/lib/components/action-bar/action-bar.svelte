<script lang="ts" module>
	import type { LucideIcon } from '@lucide/svelte';
	import type { ButtonVariant } from '#lib/components/ui/button/index.js';

	export type ActionBarAction = {
		/** Lucide icon component rendered inside the square button. */
		icon: LucideIcon;
		/** Accessible label for the icon-only button. */
		label: string;
		onclick?: () => void;
		variant?: ButtonVariant;
		disabled?: boolean;
	};

	export type ActionBarProps = {
		/** Text shown on the primary (wide) button. */
		primaryLabel: string;
		onPrimaryAction?: () => void;
		primaryVariant?: ButtonVariant;
		primaryDisabled?: boolean;
		/** 0-2 square icon-only buttons rendered after the primary button. */
		actions?: ActionBarAction[];
		class?: string;
	};
</script>

<script lang="ts">
	import { Button } from '#lib/components/ui/button/index.js';
	import { cn } from '#lib/utils.js';

	let {
		primaryLabel,
		onPrimaryAction,
		primaryVariant = 'default',
		primaryDisabled = false,
		actions = [],
		class: className
	}: ActionBarProps = $props();
</script>

<footer
	class="app-actions fixed inset-x-0 bottom-0 z-50 border-t border-border bg-background/90 backdrop-blur-md"
>
	<div
		class={cn('mx-auto flex w-full max-w-md items-center gap-2 px-3 py-2', className)}
		data-slot="action-bar"
	>
		<Button
			size="lg"
			variant={primaryVariant}
			disabled={primaryDisabled}
			onclick={onPrimaryAction}
			class="h-12 flex-1 rounded-xl px-4 text-sm font-semibold shadow-xs"
		>
			{primaryLabel}
		</Button>

		{#each actions as action (action.label)}
			{@const Icon = action.icon}
			<Button
				size="icon-lg"
				variant={action.variant ?? 'outline'}
				disabled={action.disabled}
				onclick={action.onclick}
				aria-label={action.label}
				class="size-12 shrink-0 rounded-xl shadow-xs"
			>
				<Icon class="size-5" />
			</Button>
		{/each}
	</div>
</footer>

<style>
	.app-actions {
		padding-top: 0.5rem;
		padding-bottom: max(0.75rem, env(safe-area-inset-bottom, 0px));
	}
</style>
