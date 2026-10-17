export const PERSONA_IDS = [
  'student',
  'business_owner',
  'investor',
  'first_home_buyer',
  'job_seeker',
  'family',
  'newcomer',
] as const;

export type PersonaId = (typeof PERSONA_IDS)[number];

export const MAX_PERSONAS = 3;
export const PERSONA_STORAGE_KEY = 'nk_personas';

export interface PersonaStarter {
  labelMs: string;
  labelEn: string;
  labelZh: string;
  queryMs: string;
  queryEn: string;
  queryZh: string;
}

// Starters are questions only — answers still come from the cited RAG
// pipeline, so a persona never pre-bakes a factual claim into the UI.
export const PERSONA_STARTERS: Record<PersonaId, PersonaStarter[]> = {
  student: [
    {
      labelMs: 'Pinjaman PTPTN', labelEn: 'PTPTN loan', labelZh: 'PTPTN 贷款',
      queryMs: 'Bagaimana cara memohon pinjaman PTPTN?',
      queryEn: 'How do I apply for a PTPTN loan?',
      queryZh: '如何申请 PTPTN 助学贷款？',
    },
    {
      labelMs: 'Biasiswa kerajaan', labelEn: 'Government scholarships', labelZh: '政府奖学金',
      queryMs: 'Apakah biasiswa kerajaan yang boleh dipohon oleh pelajar universiti?',
      queryEn: 'What government scholarships can university students apply for?',
      queryZh: '大学生可以申请哪些政府奖学金？',
    },
  ],
  business_owner: [
    {
      labelMs: 'Daftar syarikat', labelEn: 'Register a company', labelZh: '注册公司',
      queryMs: 'Apakah langkah-langkah untuk mendaftarkan syarikat di SSM Malaysia?',
      queryEn: 'What are the steps to register a company with SSM Malaysia?',
      queryZh: '在马来西亚SSM注册公司的步骤是什么？',
    },
    {
      labelMs: 'Geran perniagaan', labelEn: 'Grants I qualify for', labelZh: '符合资格的资助',
      queryMs: 'Apakah geran kerajaan yang saya layak mohon sebagai pemilik perniagaan kecil?',
      queryEn: 'What grants am I eligible for as a small business owner?',
      queryZh: '作为小型企业主，我可以申请哪些政府资助？',
    },
  ],
  investor: [
    {
      labelMs: 'Cukai dividen', labelEn: 'Tax on dividends', labelZh: '股息税',
      queryMs: 'Bagaimana dividen saham dikenakan cukai di Malaysia?',
      queryEn: 'How are share dividends taxed in Malaysia?',
      queryZh: '马来西亚的股票股息如何征税？',
    },
    {
      labelMs: 'Untung modal', labelEn: 'Capital gains tax', labelZh: '资本利得税',
      queryMs: 'Adakah keuntungan modal dikenakan cukai di Malaysia?',
      queryEn: 'Is capital gains tax charged in Malaysia?',
      queryZh: '马来西亚是否征收资本利得税？',
    },
  ],
  first_home_buyer: [
    {
      labelMs: 'Pengeluaran KWSP', labelEn: 'EPF for a first home', labelZh: '公积金买首套房',
      queryMs: 'Bagaimana cara mengeluarkan wang KWSP untuk pembelian rumah pertama?',
      queryEn: 'How do I withdraw EPF for first home purchase?',
      queryZh: '如何提取公积金用于购买首套房屋？',
    },
    {
      labelMs: 'Duti setem', labelEn: 'Stamp duty exemption', labelZh: '印花税豁免',
      queryMs: 'Adakah pengecualian duti setem untuk pembeli rumah pertama?',
      queryEn: 'Is there a stamp duty exemption for first-time home buyers?',
      queryZh: '首次购房者是否可享印花税豁免？',
    },
  ],
  job_seeker: [
    {
      labelMs: 'Hak pekerja', labelEn: 'Employee rights', labelZh: '员工权益',
      queryMs: 'Apakah hak pekerja di bawah Akta Kerja 1955?',
      queryEn: 'What are employee rights under the Employment Act 1955?',
      queryZh: '1955年雇佣法令下员工有哪些权益？',
    },
    {
      labelMs: 'Faedah PERKESO', labelEn: 'SOCSO if retrenched', labelZh: '失业保险',
      queryMs: 'Bagaimana cara memohon faedah PERKESO jika diberhentikan kerja?',
      queryEn: 'How do I claim SOCSO benefits if I am retrenched?',
      queryZh: '被裁员后如何申请社险（PERKESO）福利？',
    },
  ],
  family: [
    {
      labelMs: 'Bantuan keluarga', labelEn: 'Family aid', labelZh: '家庭援助',
      queryMs: 'Apakah bantuan kerajaan untuk keluarga berpendapatan rendah?',
      queryEn: 'What government aid is available for low-income families?',
      queryZh: '低收入家庭可以获得哪些政府援助？',
    },
    {
      labelMs: 'Pelepasan cukai anak', labelEn: 'Tax relief for children', labelZh: '子女税务减免',
      queryMs: 'Apakah pelepasan cukai untuk anak?',
      queryEn: 'What tax relief can I claim for my children?',
      queryZh: '我可以为子女申请哪些税务减免？',
    },
  ],
  newcomer: [
    {
      labelMs: 'Pas kerja', labelEn: 'Work passes', labelZh: '工作准证',
      queryMs: 'Apakah jenis pas kerja untuk warga asing di Malaysia?',
      queryEn: 'What types of work pass are available for foreigners in Malaysia?',
      queryZh: '外国人在马来西亚可以申请哪些类型的工作准证？',
    },
    {
      labelMs: 'Pemastautin cukai', labelEn: 'Tax residency', labelZh: '税务居民',
      queryMs: 'Bagaimana status pemastautin cukai ditentukan di Malaysia?',
      queryEn: 'How is tax residency determined in Malaysia?',
      queryZh: '马来西亚如何认定税务居民身份？',
    },
  ],
};

export function parsePersonas(raw: unknown): PersonaId[] {
  if (!Array.isArray(raw)) return [];
  const valid = raw.filter((v): v is PersonaId => PERSONA_IDS.includes(v as PersonaId));
  return Array.from(new Set(valid)).slice(0, MAX_PERSONAS);
}

export function personaStarters(personas: PersonaId[], limit = 4): PersonaStarter[] {
  // Round-robin so a 3-persona user sees one from each before any second one.
  const out: PersonaStarter[] = [];
  for (let i = 0; out.length < limit; i++) {
    let added = false;
    for (const p of personas) {
      const s = PERSONA_STARTERS[p][i];
      if (s && out.length < limit) {
        out.push(s);
        added = true;
      }
    }
    if (!added) break;
  }
  return out;
}
