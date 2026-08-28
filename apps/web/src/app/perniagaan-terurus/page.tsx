'use client';

import { Suspense, useCallback, useMemo, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { motion, useReducedMotion } from 'framer-motion';
import { LandingHeader } from '@/components/layout/LandingHeader';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useI18n } from '@/lib/i18n';
import { useTheme } from '@/lib/theme';
import { API_BASE } from '@/lib/api-base';

// Manual-sale landing page for the managed-service offer (Pro-Perniagaan +
// Kredit Ejen, reframed as "we handle your compliance & grants" instead of
// self-serve checkout) — see the kickstart plan this implements: sell the
// managed version manually to the first 3-5 clients before building any
// automation, and use this page as the concrete thing to forward in
// company-secretary/accountant referral conversations. referral_source is
// captured invisibly from ?ref= so partner conversions are measurable
// before anyone is paid commission.

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5 } },
};

type SubmitState = 'idle' | 'submitting' | 'success' | 'error';

const CONTENT = {
  ms: {
    eyebrow: 'Perkhidmatan Terurus',
    title: 'Kami Uruskan Pematuhan & Geran Anda',
    subtitle:
      'Bukan sekadar alat AI — pasukan kami menggunakan NakTahu AI Pro-Perniagaan + Kredit Ejen untuk uruskan pematuhan SSM, permohonan geran, dan tarikh akhir penting syarikat anda, hujung ke hujung.',
    ctaBook: 'Tempah Panggilan Percuma',
    included: {
      title: 'Apa Yang Termasuk',
      items: [
        { title: 'Compliance Drafter terurus', desc: 'Kami sediakan dan semak dokumen pematuhan SSM/LHDN anda, bukan anda yang menaip prom.' },
        { title: 'Grant Finder + Kredit Ejen', desc: 'Kami cari geran yang layak untuk syarikat anda dan bantu draf permohonan sehingga hantar.' },
        { title: 'Semakan WhatsApp berkala', desc: 'Kemas kini status dan peringatan tarikh akhir terus ke WhatsApp anda — bukan menunggu anda log masuk.' },
      ],
    },
    how: {
      title: 'Bagaimana Ia Berfungsi',
      steps: [
        'Tempah panggilan 15 minit — kami fahami keperluan syarikat anda',
        'Kami sediakan draf pematuhan/geran pertama menggunakan Kredit Ejen',
        'Anda semak dan luluskan — kami hantar dan pantau tarikh akhir',
      ],
    },
    disclaimerTitle: 'Nota Penting',
    disclaimer:
      'Ini adalah perkhidmatan terurus manual pada peringkat awal — bukan langganan swalayan. Kami akan hubungi anda secara peribadi untuk bincang keperluan sebelum apa-apa bayaran dibuat.',
  },
  en: {
    eyebrow: 'Managed Service',
    title: 'We Handle Your Compliance & Grants',
    subtitle:
      "Not just an AI tool — our team uses NakTahu AI's Pro-Perniagaan + Kredit Ejen to manage your company's SSM compliance, grant applications, and deadlines, end to end.",
    ctaBook: 'Book a Free Call',
    included: {
      title: "What's Included",
      items: [
        { title: 'Managed Compliance Drafter', desc: 'We prepare and review your SSM/LHDN compliance documents — you never type a prompt.' },
        { title: 'Grant Finder + Kredit Ejen', desc: 'We find grants your company qualifies for and help draft the application through to submission.' },
        { title: 'Regular WhatsApp check-ins', desc: 'Status updates and deadline reminders land straight in your WhatsApp — no need to log in and check.' },
      ],
    },
    how: {
      title: 'How It Works',
      steps: [
        'Book a 15-minute call — we learn your company’s needs',
        'We prepare your first compliance/grant draft using Kredit Ejen',
        'You review and approve — we submit and track every deadline',
      ],
    },
    disclaimerTitle: 'Important Note',
    disclaimer:
      "This is an early-stage, manually-run service — not a self-serve subscription. We'll reach out personally to discuss your needs before any payment is made.",
  },
  zh: {
    eyebrow: '托管服务',
    title: '我们为您打理合规与拨款申请',
    subtitle:
      '不只是 AI 工具——我们的团队使用 NakTahu AI 的 Pro-Perniagaan + Kredit Ejen，为贵公司全程处理 SSM 合规、拨款申请与重要期限。',
    ctaBook: '预约免费通话',
    included: {
      title: '服务内容',
      items: [
        { title: '专人处理合规文件', desc: '我们为您准备并审核 SSM/LHDN 合规文件——您无需自行输入任何提示词。' },
        { title: 'Grant Finder + Kredit Ejen', desc: '我们为贵公司寻找符合资格的拨款，并协助起草申请直至提交。' },
        { title: '定期 WhatsApp 通报', desc: '状态更新与截止日期提醒直接发送到您的 WhatsApp——无需登入查看。' },
      ],
    },
    how: {
      title: '运作方式',
      steps: [
        '预约 15 分钟通话——我们了解贵公司的需求',
        '我们使用 Kredit Ejen 准备首份合规/拨款草案',
        '您审核并批准——我们负责提交并追踪每个期限',
      ],
    },
    disclaimerTitle: '重要说明',
    disclaimer: '这是早期、人工处理的服务，并非自助订阅。我们会亲自与您联系了解需求，付款前不会有任何扣款。',
  },
};

function LeadForm({ referralSource }: { referralSource: string | null }) {
  const { t } = useI18n();
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  const [name, setName] = useState('');
  const [company, setCompany] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [message, setMessage] = useState('');
  const [state, setState] = useState<SubmitState>('idle');
  const [validationError, setValidationError] = useState<string | null>(null);

  const inputClass = 'bg-white dark:bg-white/5';
  const labelClass = `block text-xs font-semibold mb-1 ${isDark ? 'text-zinc-300' : 'text-zinc-700'}`;

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!email.trim() && !phone.trim()) {
        setValidationError(t('perniagaan.form.contact_required'));
        return;
      }
      setValidationError(null);
      setState('submitting');
      try {
        const res = await fetch(`${API_BASE}/api/v1/leads`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: name.trim(),
            company: company.trim() || null,
            contact_email: email.trim() || null,
            contact_phone: phone.trim() || null,
            message: message.trim() || null,
            referral_source: referralSource,
          }),
        });
        if (!res.ok) throw new Error('lead_submit_failed');
        setState('success');
      } catch {
        setState('error');
      }
    },
    [name, company, email, phone, message, referralSource, t],
  );

  if (state === 'success') {
    return (
      <div
        className={`rounded-2xl border p-6 text-center ${
          isDark ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300' : 'bg-emerald-50 border-emerald-200 text-emerald-700'
        }`}
      >
        {t('perniagaan.form.success')}
      </div>
    );
  }

  return (
    <form
      onSubmit={(e) => void handleSubmit(e)}
      className={`rounded-2xl border p-6 space-y-4 ${isDark ? 'bg-white/5 border-white/10' : 'bg-white border-zinc-200 shadow-sm'}`}
    >
      <div>
        <label className={labelClass}>{t('perniagaan.form.name_label')}</label>
        <Input
          required
          maxLength={200}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={t('perniagaan.form.name_placeholder')}
          className={inputClass}
        />
      </div>
      <div>
        <label className={labelClass}>{t('perniagaan.form.company_label')}</label>
        <Input
          maxLength={200}
          value={company}
          onChange={(e) => setCompany(e.target.value)}
          placeholder={t('perniagaan.form.company_placeholder')}
          className={inputClass}
        />
      </div>
      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <label className={labelClass}>{t('perniagaan.form.email_label')}</label>
          <Input
            type="email"
            maxLength={320}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder={t('perniagaan.form.email_placeholder')}
            className={inputClass}
          />
        </div>
        <div>
          <label className={labelClass}>{t('perniagaan.form.phone_label')}</label>
          <Input
            type="tel"
            maxLength={32}
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder={t('perniagaan.form.phone_placeholder')}
            className={inputClass}
          />
        </div>
      </div>
      <p className={`text-xs -mt-2 ${isDark ? 'text-zinc-500' : 'text-zinc-400'}`}>{t('perniagaan.form.contact_hint')}</p>
      <div>
        <label className={labelClass}>{t('perniagaan.form.message_label')}</label>
        <textarea
          maxLength={2000}
          rows={3}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder={t('perniagaan.form.message_placeholder')}
          className={`w-full rounded-xl border px-3 py-2 text-sm bg-transparent transition-colors focus:outline-none focus:ring-1 ${
            isDark
              ? 'border-white/10 focus:border-nk-official/50 focus:ring-nk-official/30 placeholder:text-zinc-500'
              : 'border-zinc-200 focus:border-nk-official/50 focus:ring-nk-official/30 placeholder:text-zinc-400'
          }`}
        />
      </div>

      {validationError && <p className="text-sm text-red-600 dark:text-red-400">{validationError}</p>}
      {state === 'error' && <p className="text-sm text-red-600 dark:text-red-400">{t('perniagaan.form.error')}</p>}

      <Button type="submit" size="lg" disabled={state === 'submitting'} className="w-full">
        {state === 'submitting' ? t('perniagaan.form.submitting') : t('perniagaan.form.submit')}
      </Button>
    </form>
  );
}

function PerniagaanTerurusInner() {
  const { locale } = useI18n();
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const reduceMotion = useReducedMotion();
  const searchParams = useSearchParams();
  const referralSource = useMemo(() => searchParams.get('ref'), [searchParams]);

  const c = locale === 'zh' ? CONTENT.zh : locale === 'en' ? CONTENT.en : CONTENT.ms;

  return (
    <div className={`flex flex-col h-full font-sans ${isDark ? 'bg-[#12151C] text-white' : 'bg-zinc-50 text-zinc-900'}`}>
      <LandingHeader />

      <main className="flex-1 min-h-0 overflow-y-auto">
        <div className="max-w-4xl mx-auto w-full px-4 sm:px-6 py-12">
          <motion.div initial="hidden" animate="show" variants={fadeUp} className="space-y-12">
            <header className="text-center space-y-3">
              <span
                className={`inline-block text-[11px] font-bold uppercase tracking-wide px-3 py-1 rounded-full ${
                  isDark ? 'bg-nk-official/15 text-nk-official' : 'bg-nk-official/10 text-nk-official-dim'
                }`}
              >
                {c.eyebrow}
              </span>
              <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight text-balance">{c.title}</h1>
              <p className={`text-lg max-w-2xl mx-auto text-balance ${isDark ? 'text-zinc-400' : 'text-zinc-500'}`}>
                {c.subtitle}
              </p>
            </header>

            <section className="space-y-6">
              <h2 className={`text-2xl font-bold text-center ${isDark ? 'text-nk-official' : 'text-nk-official-dim'}`}>
                {c.included.title}
              </h2>
              <div className="grid md:grid-cols-3 gap-5">
                {c.included.items.map((item, i) => (
                  <motion.div
                    key={i}
                    initial={reduceMotion ? false : { opacity: 0, y: 16 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, amount: 0.5 }}
                    transition={{ duration: 0.4, delay: reduceMotion ? 0 : i * 0.1, ease: 'easeOut' }}
                    className={`rounded-2xl p-5 border ${isDark ? 'bg-white/5 border-white/10' : 'bg-white border-zinc-200 shadow-sm'}`}
                  >
                    <h3 className={`font-semibold mb-1.5 ${isDark ? 'text-white' : 'text-zinc-900'}`}>{item.title}</h3>
                    <p className={`text-sm leading-relaxed ${isDark ? 'text-zinc-400' : 'text-zinc-500'}`}>{item.desc}</p>
                  </motion.div>
                ))}
              </div>
            </section>

            <section className="space-y-6">
              <h2 className={`text-2xl font-bold text-center ${isDark ? 'text-nk-official' : 'text-nk-official-dim'}`}>
                {c.how.title}
              </h2>
              <ol className="max-w-xl mx-auto space-y-3">
                {c.how.steps.map((step, i) => (
                  <li key={i} className="flex items-start gap-3">
                    <span
                      className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold ${
                        isDark ? 'bg-nk-official/20 text-nk-official' : 'bg-nk-official/15 text-nk-official-dim'
                      }`}
                    >
                      {i + 1}
                    </span>
                    <span className={`pt-0.5 text-sm leading-relaxed ${isDark ? 'text-zinc-300' : 'text-zinc-700'}`}>{step}</span>
                  </li>
                ))}
              </ol>
            </section>

            <section className="max-w-lg mx-auto w-full space-y-4">
              <h2 className={`text-2xl font-bold text-center ${isDark ? 'text-nk-official' : 'text-nk-official-dim'}`}>
                {c.ctaBook}
              </h2>
              <LeadForm referralSource={referralSource} />
            </section>

            <section
              className={`max-w-2xl mx-auto rounded-xl p-5 border text-sm leading-relaxed ${
                isDark ? 'bg-amber-500/10 border-amber-500/20 text-zinc-300' : 'bg-amber-50 border-amber-200 text-zinc-600'
              }`}
            >
              <p className={`font-semibold mb-1 ${isDark ? 'text-amber-300' : 'text-amber-700'}`}>{c.disclaimerTitle}</p>
              <p>{c.disclaimer}</p>
            </section>
          </motion.div>
        </div>
      </main>

      <footer
        className={`border-t px-6 py-6 flex flex-col sm:flex-row items-center justify-center gap-4 text-sm ${
          isDark ? 'border-white/10 text-zinc-500' : 'border-zinc-200 text-zinc-500'
        }`}
      >
        <Link href="/" className={`transition-colors ${isDark ? 'hover:text-white' : 'hover:text-zinc-900'}`}>
          &larr; NakTahu AI
        </Link>
      </footer>
    </div>
  );
}

export default function PerniagaanTerurusPage() {
  return (
    <Suspense>
      <PerniagaanTerurusInner />
    </Suspense>
  );
}
