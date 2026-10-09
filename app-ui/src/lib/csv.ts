export type Recipient = {
	name: string;
	phone: string;
	language: string;
	segment: string;
};

export const RECIPIENT_COLUMNS = ['name', 'phone', 'language', 'segment'] as const;

export const SAMPLE_RECIPIENTS: Recipient[] = [
	{ name: 'Ananya Sharma', phone: '+91 98••• ••210', language: 'Hindi', segment: 'Patron' },
	{ name: 'Karthik Iyer', phone: '+91 99••• ••845', language: 'Tamil', segment: 'Alumni' },
	{ name: 'Meera Nair', phone: '+91 97••• ••019', language: 'Malayalam', segment: 'Parent' },
	{ name: 'Rohan Gupta', phone: '+91 96••• ••733', language: 'Marathi', segment: 'Patient' }
];

function splitLine(line: string): string[] {
	const cells: string[] = [];
	let current = '';
	let quoted = false;

	for (let i = 0; i < line.length; i++) {
		const char = line[i];
		if (quoted) {
			if (char === '"') {
				if (line[i + 1] === '"') {
					current += '"';
					i++;
				} else {
					quoted = false;
				}
			} else {
				current += char;
			}
		} else if (char === '"') {
			quoted = true;
		} else if (char === ',') {
			cells.push(current);
			current = '';
		} else {
			current += char;
		}
	}

	cells.push(current);
	return cells.map((cell) => cell.trim());
}

export function parseRecipients(text: string): Recipient[] {
	const lines = text.split(/\r?\n/).filter((line) => line.trim().length > 0);
	if (lines.length === 0) return [];

	const header = splitLine(lines[0]).map((cell) => cell.toLowerCase());
	const hasHeader = header.includes('name') || header.includes('phone');
	const rows = hasHeader ? lines.slice(1) : lines;

	return rows
		.map((line) => {
			const [name = '', phone = '', language = '', segment = ''] = splitLine(line);
			return { name, phone, language, segment };
		})
		.filter((row) => row.name || row.phone);
}
