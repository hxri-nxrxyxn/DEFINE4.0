const URL = 'https://define-hack-default-rtdb.firebaseio.com/campaigns.json';

const firstNames = {
  Hindi: ['Ananya','Rohan','Vikram','Priya','Aarav','Isha','Kabir','Neha','Arjun','Sneha'],
  Tamil: ['Karthik','Divya','Naveen','Meena','Suresh','Lakshmi','Vignesh','Anitha'],
  Telugu: ['Sneha','Ravi','Keerthi','Harsha','Lavanya','Pavan','Sruthi','Manoj'],
  Malayalam: ['Meera','Akhil','Anjali','Nithin','Reshma','Vishnu','Sreya','Arun'],
  Marathi: ['Rohan','Sai','Omkar','Pallavi','Yash','Gauri','Tanvi','Aditya'],
  Kannada: ['Divya','Manoj','Deepa','Kiran','Shreya','Rahul','Pooja','Anil'],
  Bengali: ['Arjun','Riya','Sourav','Mou','Debjit','Ishita','Tuhin','Payel'],
  English: ['Alex','Sara','David','Maya','Rahul','Nina']
};
const surnames = ['Sharma','Iyer','Nair','Reddy','Das','Menon','Singh','Rao','Patel','Gupta','Kumar','Sheikh'];

let phoneSeq = 9821000000;

function makeRecipients(count, languages, segments) {
  const recs = [];
  for (let i = 0; i < count; i++) {
    const lang = languages[i % languages.length];
    const fn = firstNames[lang][i % firstNames[lang].length];
    const ln = surnames[i % surnames.length];
    recs.push({
      name: `${fn} ${ln}`,
      phone: String(phoneSeq++),
      language: lang,
      segment: segments[i % segments.length]
    });
  }
  return recs;
}

const dispositions = ['confirmed','confirmed','confirmed','confirmed','confirmed','declined','not_available','no_response','opt_out'];

function makeCalls(recs, campaignName, hopMs) {
  const calls = {};
  const base = Date.now() - recs.length * hopMs;
  recs.forEach((r, i) => {
    const d = dispositions[Math.floor(Math.random() * dispositions.length)];
    calls['c' + i] = {
      ...r,
      disposition: d,
      attempts: 1 + (i % 2),
      durationSec: 12 + Math.floor(Math.random() * 78),
      ts: base + i * hopMs + Math.floor(Math.random() * 5000),
      campaign: campaignName
    };
  });
  return calls;
}

const campaigns = {};

// 1. Flagship seminar campaign
{
  const recs = makeRecipients(48, ['Hindi','Tamil','Telugu','Malayalam','Marathi','Kannada','Bengali','English'], ['Parent','Alumni','Student','Staff']);
  campaigns['cmp_seminar'] = {
    meta: { name: 'National AI & Healthcare Seminar 2026', domain: 'events', script: 'Hello {name}, you are invited to the National AI & Healthcare Seminar in Mumbai on Saturday at 10 AM. Press 1 to confirm, 2 to reschedule, or 9 to opt out.', createdAt: Date.now() - 3 * 3600 * 1000 },
    recipients: Object.fromEntries(recs.map((r, i) => ['r' + i, r])),
    calls: makeCalls(recs, 'National AI & Healthcare Seminar 2026', 42000)
  };
}

// 2. Clinic reminders
{
  const recs = makeRecipients(26, ['Hindi','Malayalam','Tamil','Telugu'], ['Patient','Parent']);
  campaigns['cmp_clinic'] = {
    meta: { name: 'City Health Clinic Appointment Reminders', domain: 'clinic', script: 'Hello {name}, this is a reminder for your appointment at City Health Clinic tomorrow at 3 PM.', createdAt: Date.now() - 2 * 3600 * 1000 },
    recipients: Object.fromEntries(recs.map((r, i) => ['r' + i, r])),
    calls: makeCalls(recs, 'City Health Clinic Appointment Reminders', 55000)
  };
}

// 3. School-parent PTA
{
  const recs = makeRecipients(22, ['Hindi','Telugu','Kannada','English'], ['Parent','Staff']);
  campaigns['cmp_school'] = {
    meta: { name: 'Greenwood School PTA Sync', domain: 'school', script: 'Hello {name}, the annual Parent-Teacher meeting is this Friday at 4 PM in the main auditorium.', createdAt: Date.now() - 90 * 60 * 1000 },
    recipients: Object.fromEntries(recs.map((r, i) => ['r' + i, r])),
    calls: makeCalls(recs, 'Greenwood School PTA Sync', 60000)
  };
}

// 4. Payment reminders
{
  const recs = makeRecipients(16, ['Hindi','Tamil','Marathi','English'], ['Customer','Enterprise']);
  campaigns['cmp_payment'] = {
    meta: { name: 'Monthly Invoice Reminders', domain: 'payment', script: 'Hello {name}, your invoice is due tomorrow. Please confirm payment.', createdAt: Date.now() - 45 * 60 * 1000 },
    recipients: Object.fromEntries(recs.map((r, i) => ['r' + i, r])),
    calls: makeCalls(recs, 'Monthly Invoice Reminders', 70000)
  };
}

const res = await fetch(URL, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(campaigns) });
console.log('status', res.status, 'body', (await res.text()).slice(0, 80));

const counts = Object.entries(campaigns).map(([k, v]) => `${k}: ${Object.keys(v.calls).length} calls`);
console.log('seeded ->', counts.join(' | '));
