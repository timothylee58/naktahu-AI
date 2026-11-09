import type { Metadata } from 'next';
import { LegalLayout, type LegalSection } from '@/components/legal/LegalLayout';

export const metadata: Metadata = {
  title: 'Privacy Policy — NakTahu AI',
  description: 'How NakTahu AI collects, uses, and protects your personal data.',
};

const EFFECTIVE_DATE = '30 May 2026';

// Policy text is unchanged from the previous page; only the presentation
// moved to the shared LegalLayout (theme tokens, section anchors, index).
const SECTIONS: readonly LegalSection[] = [
  {
    id: 'introduction',
    title: '1. Introduction',
    content: (
      <>
            <p>
              NakTahu AI (&ldquo;we&rdquo;, &ldquo;our&rdquo;, or &ldquo;the Service&rdquo;) is a Malaysian civic knowledge
              assistant that helps users find information about public services, government procedures,
              education, finance, healthcare, and related civic affairs.
            </p>
            <p>
              This Privacy Policy explains what data we collect, how we use it, and your rights over it.
              By using NakTahu AI you agree to the practices described here.
            </p>
      </>
    ),
  },
  {
    id: 'data-we-collect',
    title: '2. Data We Collect',
    content: (
      <>
            <h3>2.1 Data you provide</h3>
              <ul>
                <li><strong>Account information</strong> — email address when you sign in via Email Magic Link or Google OAuth.</li>
                <li><strong>Query text</strong> — the questions you submit to the AI assistant.</li>
                <li><strong>Answers and citations</strong> — on plans that include History (currently Pro), the full text of each answer (with its citations, confidence score and suggested follow-ups) is saved with your query so History can show you exactly what you saw.</li>
              </ul>
            <h3>2.2 Data collected automatically</h3>
              <ul>
                <li><strong>Anonymous session ID</strong> — a randomly generated UUID stored in your browser&rsquo;s localStorage before sign-in, used solely to migrate your pre-login history to your account upon sign-in.</li>
                <li><strong>Query metadata</strong> — detected language, domain category (e.g. tax, EPF), confidence score, and timestamp stored alongside your query history.</li>
                <li><strong>Error and performance data</strong> — anonymised error events sent to Sentry for debugging. These do not include your query content.</li>
                <li><strong>Experiment traces</strong> — anonymised pipeline traces (latency, token count, model used) sent to Weights &amp; Biases Weave for model quality monitoring. These do not include your account identity.</li>
              </ul>
            <h3>2.3 Data we do NOT collect</h3>
              <ul>
                <li>We do not collect payment information.</li>
                <li>We do not collect device fingerprints or persistent tracking cookies.</li>
                                <li>We do not store the household/eligibility details you enter into the Welfare Eligibility Agent (Check Assistance) — see 2.4 below.</li>
              </ul>
            <h3>2.4 Welfare Eligibility Agent — stateless processing</h3>
              <p>
                The Welfare Eligibility Agent (&ldquo;Check Assistance&rdquo;) asks for demographic, household, and
                status information to match you against cost-of-living assistance schemes. This information —
                birth year, income, dependents, employment/education/housing status, and similar fields — is
                processed <strong>in memory for the single request that generates your result, and is not written
                to our database</strong>. Once your result is returned, that information is discarded; we retain
                no record of the specific answers you gave. This mirrors the stateless-intake approach used by
                Malaysia&rsquo;s own Ihsan MADANI portal for the same category of information.
              </p>
            <h3>2.5 Calendar sync (Deadline Monitor)</h3>
              <p>
                If you connect a Google or Microsoft calendar to Deadline Monitor, we store an{' '}
                <strong>encrypted refresh token</strong> for that account so we can add and update deadline
                events on your behalf. We request write access to your calendar events only —{' '}
                <strong>we do not read your existing calendar events, meetings, or availability</strong>. On
                Google this is enforced by the narrower <code>calendar.events</code> permission; Microsoft
                Graph offers no write-only equivalent, so its permission is technically read-and-write even
                though we never read.
              </p>
              <p>
                The only data we write is the deadline name, its due date, and a link to the official source
                — all of which already come from public government sources, not from you. Disconnecting a
                calendar deletes the stored token immediately (and revokes it at Google&rsquo;s end, where
                revocation is supported); events already added remain in your calendar for you to keep or
                delete.
              </p>

      </>
    ),
  },
  {
    id: 'how-we-use-your-data',
    title: '3. How We Use Your Data',
    content: (
      <>
            <ul>
              <li><strong>To provide the service</strong> — routing your query through the AI pipeline and returning an answer.</li>
              <li><strong>Query history</strong> — saving your recent questions and the answers you received, per account on plans that include History (currently Pro), so you can revisit them.</li>
              <li><strong>Rate limiting</strong> — keying anonymous users (30 req/hr) and authenticated users (200 req/hr) to prevent abuse.</li>
              <li><strong>Service improvement</strong> — anonymised traces help us tune model quality and latency.</li>
            </ul>
      </>
    ),
  },
  {
    id: 'data-storage-and-retention',
    title: '4. Data Storage and Retention',
    content: (
      <>
            <ul>
              <li><strong>Authentication data</strong> is stored by <a href="https://supabase.com/privacy" target="_blank" rel="noopener noreferrer">Supabase</a> (hosted on AWS ap-southeast-1).</li>
              <li><strong>Query history</strong> (your questions, the full answers and their citations) is saved in our Supabase database against your account until you delete it or your account is deleted; it is not automatically expired. A temporary copy of your most recent entries is also kept in Redis for speed and expires after 30 days of inactivity. History shows your 20 most recent entries. You can delete individual entries from the History page.</li>
              <li><strong>Account deletion</strong> — you may request deletion of your account and all associated data by emailing us. We will process requests within 14 days.</li>
            </ul>
      </>
    ),
  },
  {
    id: 'third-party-services',
    title: '5. Third-Party Services',
    content: (
      <>
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
      </>
    ),
  },
  {
    id: 'cookies-and-local-storage',
    title: '6. Cookies and Local Storage',
    content: (
      <>
            <p>
              We use <strong>browser localStorage</strong> only to store your anonymous session ID and UI language preference.
              We do not use advertising cookies or third-party tracking pixels.
              Supabase stores an authentication session token in a secure cookie after sign-in.
            </p>
      </>
    ),
  },
  {
    id: 'your-rights',
    title: '7. Your Rights',
    content: (
      <>
            <p>Under Malaysia&rsquo;s <strong>Personal Data Protection Act 2010 (PDPA)</strong> and, where applicable, GDPR, you have the right to:</p>
            <ul>
              <li>Access the personal data we hold about you.</li>
              <li>Correct inaccurate data.</li>
              <li>Request deletion of your data.</li>
              <li>Withdraw consent at any time by deleting your account.</li>
            </ul>
            <p>To exercise these rights, contact us at the email below.</p>
      </>
    ),
  },
  {
    id: 'children',
    title: '8. Children',
    content: (
      <>
            <p>
              NakTahu AI is not directed at children under 13. We do not knowingly collect personal data from
              children. If you believe a child has provided us data, please contact us for removal.
            </p>
      </>
    ),
  },
  {
    id: 'changes-to-this-policy',
    title: '9. Changes to This Policy',
    content: (
      <>
            <p>
              We may update this policy from time to time. Material changes will be announced via a notice on the
              website at least 7 days before they take effect. Continued use after the effective date constitutes
              acceptance.
            </p>
      </>
    ),
  },
  {
    id: 'contact',
    title: '10. Contact',
    content: (
      <>
            <p>
              For privacy questions or data requests, contact us at:{' '}
              <a href="mailto:privacy@naktahu.my">
                privacy@naktahu.my
              </a>
            </p>
      </>
    ),
  },
];

export default function PrivacyPage() {
  return <LegalLayout title="Privacy Policy" meta={`Effective date: ${EFFECTIVE_DATE}`} sections={SECTIONS} />;
}
