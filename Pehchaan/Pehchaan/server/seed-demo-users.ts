import dotenv from 'dotenv';
dotenv.config();

import bcrypt from 'bcryptjs';
import { rememberUser, verifyOffline } from './offline-auth.ts';

const users = [
  {
    id: 'USR-OFFICER-001',
    email: 'officer@pehchaan.gov.in',
    name: 'Officer Rajesh Kumar',
    role: 'OFFICER',
    checkpoint_ids: ['CP-001'],
    password_hash: bcrypt.hashSync('officer123', 10),
    must_change_password: false,
  },
  {
    id: 'USR-INCHARGE-001',
    email: 'incharge@pehchaan.gov.in',
    name: 'In-Charge Vikram Singh',
    role: 'POST_INCHARGE',
    checkpoint_ids: ['CP-001'],
    password_hash: bcrypt.hashSync('incharge123', 10),
    must_change_password: false,
  },
  {
    id: 'USR-ADMIN-001',
    email: 'admin@pehchaan.gov.in',
    name: 'Administrator',
    role: 'ADMIN',
    checkpoint_ids: ['CP-001'],
    password_hash: bcrypt.hashSync('ABC@12345678', 10),
    must_change_password: false,
  },
];

for (const u of users) {
  rememberUser(u);
  console.log(`Cached demo user: ${u.email}`);
}

// Verify
async function check() {
  const v = await verifyOffline('officer@pehchaan.gov.in', 'officer123');
  console.log('Test verify officer:', v.ok ? 'SUCCESS' : 'FAILED');
}
check();
