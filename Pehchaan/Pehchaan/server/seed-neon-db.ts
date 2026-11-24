import './bootstrap-secrets.ts';
import bcrypt from 'bcryptjs';
import { getNeonPool, initNeonSchema } from './neon.ts';

async function seed() {
  const pool = getNeonPool();
  if (!pool) {
    console.error('Failed to get Neon pool');
    process.exit(1);
  }

  console.log('Initializing Neon database schema...');
  await initNeonSchema();
  console.log('Schema initialized successfully!');

  // Insert default checkpoint
  await pool.query(`
    INSERT INTO pehchaan_checkpoints (id, name, location, type)
    VALUES ('CP-001', 'Checkpoint 1 - Main Gate', 'Border Post Alpha', 'ICP')
    ON CONFLICT (id) DO NOTHING;
  `);
  console.log('Default checkpoint CP-001 created/verified.');

  const demoUsers = [
    {
      id: 'USR-OFFICER-001',
      email: 'officer@pehchaan.gov.in',
      name: 'Officer Rajesh Kumar',
      role: 'OFFICER',
      checkpointIds: ['CP-001'],
      password: 'officer123',
    },
    {
      id: 'USR-INCHARGE-001',
      email: 'incharge@pehchaan.gov.in',
      name: 'In-Charge Vikram Singh',
      role: 'POST_INCHARGE',
      checkpointIds: ['CP-001'],
      password: 'incharge123',
    },
    {
      id: 'USR-ADMIN-001',
      email: 'admin@pehchaan.gov.in',
      name: 'Administrator',
      role: 'ADMIN',
      checkpointIds: ['CP-001'],
      password: 'ABC@12345678',
    },
  ];

  for (const u of demoUsers) {
    const hash = await bcrypt.hash(u.password, 12);
    await pool.query(`
      INSERT INTO pehchaan_users (id, email, name, password_hash, role, checkpoint_ids, must_change_password)
      VALUES ($1, $2, $3, $4, $5, $6, false)
      ON CONFLICT (id) DO UPDATE SET password_hash = EXCLUDED.password_hash, must_change_password = false
    `, [u.id, u.email, u.name, hash, u.role, u.checkpointIds]);
    console.log(`Seeded user in Neon DB: ${u.email} (${u.role})`);
  }

  console.log('All demo users seeded in Neon PostgreSQL!');
  await pool.end();
}

seed().catch((err) => {
  console.error('Seeding error:', err);
  process.exit(1);
});
