import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Privacy Policy — NakTahu AI',
  description: 'How NakTahu AI collects, uses, and protects your personal data.',
};

const EFFECTIVE_DATE = '30 May 2026';

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-zinc-50">
      {/* Header */}
      <header className="bg-white border-b border-zinc-200 px-4 py-3 flex items-center gap-3 sticky top-0 z-10">
        <Link href="/" className="p-1 rounded hover:bg-zinc-100 text-zinc-500 transition-colors">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
            <path fillRule="evenodd" d="M17 10a.75.75 0 0 1-.75.75H5.612l4.158 3.96a.75.75 0 1 1-1.04 1.08l-5.5-5.25a.75.75 0 0 1 0-1.08l5.5-5.25a.75.75 0 1 1 1.04 1.08L5.612 9.25H16.25A.75.75 0 0 1 17 10Z" clipRule="evenodd" />
          </svg>
        </Link>
        <div>
          <span className="font-semibold text-zinc-900 text-sm">NakTahu AI</span>
          <span className="text-zinc-400 text-sm mx-2">·</span>
          <span className="text-zinc-500 text-sm">Privacy Policy</span>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-3xl mx-auto px-4 py-10 pb-20">
        <div className="bg-white rounded-2xl border border-zinc-100 shadow-sm px-8 py-10 flex flex-col gap-8">
          {/* Title */}
          <div>
            <h1 className="text-2xl font-bold text-zinc-900">Privacy Policy</h1>
            <p className="text-sm text-zinc-500 mt-1">Effective date: {EFFECTIVE_DATE}</p>
          </div>

          <Section title="1. Introduction">
            <p>
              NakTahu AI (&ldquo;we&rdquo;, &ldquo;our&rdquo;, or &ldquo;the Service&rdquo;) is a Malaysian civic knowledge
              assistant that helps users find information about public services, government procedures,
              education, finance, healthcare, and related civic affairs.
            </p>
            <p>
              This Privacy Policy explains what data we collect, how we use it, and your rights over it.
              By using NakTahu AI you agree to the practices described here.
            </p>
          </Section>

          <Section title="2. Data We Collect">
            <Subsection title="2.1 Data you provide">
              <ul>
                <li><strong>Account information</strong> — email address when you sign in via Email Magic Link or Google OAuth.</li>
                <li><strong>Query text</strong> — the questions you submit to the AI assistant.</li>
              </ul>
            </Subsection>
            <Subsection title="2.2 Data collected automatically">
              <ul>
                <li><strong>Anonymous session ID</strong> — a randomly generated UUID stored in your browser&rsquo;s localStorage before sign-in, used solely to migrate your pre-login history to your account upon sign-in.</li>
                <li><strong>Query metadata</strong> — detected language, domain category (e.g. tax, EPF), confidence score, and timestamp stored alongside your query history.</li>
                <li><strong>Error and performance data</strong> — anonymised error events sent to Sentry for debugging. These do not include your query content.</li>
                <li><strong>Experiment traces</strong> — anonymised pipeline traces (latency, token count, model used) sent to Weights &amp; Biases Weave for model quality monitoring. These do not include your account identity.</li>
              </ul>
            </Subsection>
            <Subsection title="2.3 Data we do NOT collect">
              <ul>
                <li>We do not collect payment information.</li>
                <li>We do not collect device fingerprints or persistent tracking cookies.</li>
                <li>We do not store the full AI-generated responses server-side — only a short summary for history display.</li>
                <li>We do not store the household/eligibility details you enter into the Welfare Eligibility Agent (Check Assistance) — see 2.4 below.</li>
              </ul>
            </Subsection>
            <Subsection title="2.4 Welfare Eligibility Agent — stateless processing">
              <p>
                The Welfare Eligibility Agent (&ldquo;Check Assistance&rdquo;) asks for demographic, household, and
                status information to match you against cost-of-living assistance schemes. This information —
                birth year, income, dependents, employment/education/housing status, and similar fields — is
                processed <strong>in memory for the single request that generates your result, and is not written
                to our database</strong>. Once your result is returned, that information is discarded; we retain
                no record of the specific answers you gave. This mirrors the stateless-intake approach used by
                Malaysia&rsquo;s own Ihsan MADANI portal for the same category of information.
              </p>
            </Subsection>
          </Section>

          <Section title="3. How We Use Your Data">
            <ul>
              <li><strong>To provide the service</strong> — routing your query through the AI pipeline and returning an answer.</li>
              <li><strong>Query history</strong> — storing up to 50 recent queries per account in Redis (TTL 30 days) so you can revisit past questions.</li>
              <li><strong>Rate limiting</strong> — keying anonymous users (30 req/hr) and authenticated users (200 req/hr) to prevent abuse.</li>
              <li><strong>Service improvement</strong> — anonymised traces help us tune model quality and latency.</li>
            </ul>
          </Section>

          <Section title="4. Data Storage and Retention">
            <ul>
              <li><strong>Authentication data</strong> is stored by <a href="https://supabase.com/privacy" className="text-nk-official-dim hover:underline" target="_blank" rel="noopener noreferrer">Supabase</a> (hosted on AWS ap-southeast-1).</li>
              <li><strong>Query history</strong> is stored in Redis with a 30-day rolling TTL. History is automatically deleted after 30 days of inactivity.</li>
              <li><strong>Account deletion</strong> — you may request deletion of your account and all associated data by emailing us. We will process requests within 14 days.</li>
            </ul>
          </Section>

          <Section title="5. Third-Party Services">
            <p>NakTahu AI uses the following third-party providers. Each has its own privacy policy.</p>
            <table>
              <thead>
                <tr>
                  <th>Provider</th>
                  <th>Purpose</th>
                </tr>
              </thead>
              <tbody>
                <tr><td>Supabase</td><td>Authentication and database</td></tr>
                <tr><td>Anthropic</td><td>AI language model (fallback synthesis)</td></tr>
                <tr><td>ILMU API (Malaysia)</td><td>AI language model (primary)</td></tr>
                <tr><td>Sentry</td><td>Error monitoring</td></tr>
                <tr><td>Weights &amp; Biases</td><td>Model experiment tracking</td></tr>
                <tr><td>Vercel</td><td>Frontend hosting</td></tr>
                <tr><td>Render</td><td>Backend API hosting</td></tr>
              </tbody>
            </table>
            <p>
              We do not sell your data to any third party.
            </p>
          </Section>

          <Section title="6. Cookies and Local Storage">
            <p>
              We use <strong>browser localStorage</strong> only to store your anonymous session ID and UI language preference.
              We do not use advertising cookies or third-party tracking pixels.
              Supabase stores an authentication session token in a secure cookie after sign-in.
            </p>
          </Section>

          <Section title="7. Your Rights">
            <p>Under Malaysia&rsquo;s <strong>Personal Data Protection Act 2010 (PDPA)</strong> and, where applicable, GDPR, you have the right to:</p>
            <ul>
              <li>Access the personal data we hold about you.</li>
              <li>Correct inaccurate data.</li>
              <li>Request deletion of your data.</li>
              <li>Withdraw consent at any time by deleting your account.</li>
            </ul>
            <p>To exercise these rights, contact us at the email below.</p>
          </Section>

          <Section title="8. Children">
            <p>
              NakTahu AI is not directed at children under 13. We do not knowingly collect personal data from
              children. If you believe a child has provided us data, please contact us for removal.
            </p>
          </Section>

          <Section title="9. Changes to This Policy">
            <p>
              We may update this policy from time to time. Material changes will be announced via a notice on the
              website at least 7 days before they take effect. Continued use after the effective date constitutes
              acceptance.
            </p>
          </Section>

          <Section title="10. Contact">
            <p>
              For privacy questions or data requests, contact us at:{' '}
              <a href="mailto:privacy@naktahu.my" className="text-nk-official-dim hover:underline">
                privacy@naktahu.my
              </a>
            </p>
          </Section>

          <div className="pt-4 border-t border-zinc-100 text-center">
            <Link href="/" className="text-sm text-zinc-400 hover:text-zinc-600 transition-colors">
              ← Back to NakTahu AI
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-base font-bold text-zinc-800">{title}</h2>
      <div className="text-sm text-zinc-600 leading-relaxed flex flex-col gap-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:flex [&_ul]:flex-col [&_ul]:gap-1.5 [&_table]:w-full [&_table]:text-left [&_table]:border-collapse [&_th]:pb-1 [&_th]:border-b [&_th]:border-zinc-200 [&_th]:font-semibold [&_th]:text-zinc-700 [&_td]:py-1.5 [&_td]:pr-4 [&_td]:border-b [&_td]:border-zinc-100">
        {children}
      </div>
    </section>
  );
}

function Subsection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <h3 className="text-sm font-semibold text-zinc-700">{title}</h3>
      {children}
    </div>
  );
}
