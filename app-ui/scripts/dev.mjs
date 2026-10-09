import { spawn } from 'node:child_process';
import net from 'node:net';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const appUiDir = path.resolve(here, '..');
const repoRoot = path.resolve(appUiDir, '..');
const viteBin = path.join(appUiDir, 'node_modules', '.bin', 'vite');

const procs = [];

function start(command, args, cwd, label) {
	const child = spawn(command, args, { cwd, stdio: 'inherit', env: process.env });
	child.on('error', (e) => console.warn(`[dev] ${label} failed to start: ${e.message}`));
	child.on('exit', (code) => {
		if (label === 'core' && code) console.warn(`[dev] core server exited with code ${code}`);
	});
	procs.push(child);
	return child;
}

function portInUse(port) {
	return new Promise((resolve) => {
		const server = net.createServer();
		server.once('error', () => resolve(true));
		server.once('listening', () => server.close(() => resolve(false)));
		server.listen(port, '127.0.0.1');
	});
}

// Auto-start the Python core platform API (analytics, retry, Exotel dispatch).
if (await portInUse(8000)) {
	console.log('[dev] core API already listening on :8000 — not starting another.');
} else {
	console.log('[dev] starting core API on :8000');
	start('python3', [path.join(repoRoot, 'core', 'api_server.py'), '--host', '0.0.0.0', '--port', '8000'], repoRoot, 'core');
}

// Start the SvelteKit dev server (bound to all interfaces so phones can connect).
start(viteBin, ['dev', '--host'], appUiDir, 'vite');

function shutdown() {
	for (const p of procs) {
		try {
			p.kill('SIGTERM');
		} catch {}
	}
	process.exit(0);
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
