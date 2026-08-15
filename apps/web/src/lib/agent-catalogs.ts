import type { ChipOption } from '@/components/agents/ChipSelector';

// Shared between grant-finder and grant-draft-generator — both pages
// independently hardcoded near-identical English-only SECTOR_OPTIONS/
// BUSINESS_TYPE_OPTIONS arrays (grant-draft-generator's own comment even
// says "same seed values as grant-finder's ChipSelector options"), which
// meant every chip on both pages showed English text regardless of UI
// locale, AND the two copies could silently drift out of sync. Extracted
// here as the single source of truth: ids match grant_database.
// eligible_sectors / eligibility_agent's business_type enum exactly (a
// mismatch here silently zeroes out grant matches), only the display
// `label` is localized.
//
// businessTypeOptions is identical between the two pages. sectorOptions
// covers the shared base set; extendedSectorOptions is grant-finder's
// superset (adds deeptech/biotech/agriculture) — kept as an explicit
// separate list rather than derived by splicing, so each page's exact
// option set stays easy to read at a glance.

export function sectorOptions(t: (key: string) => string): ChipOption[] {
  return [
    { id: 'technology', label: t('agents.sector.technology'), icon: '🖥' },
    { id: 'ai', label: t('agents.sector.ai'), icon: '🤖' },
    { id: 'fintech', label: t('agents.sector.fintech'), icon: '💳' },
    { id: 'edtech', label: t('agents.sector.edtech'), icon: '📚' },
    { id: 'healthtech', label: t('agents.sector.healthtech'), icon: '⚕️' },
    { id: 'digital', label: t('agents.sector.digital'), icon: '📱' },
    { id: 'manufacturing', label: t('agents.sector.manufacturing'), icon: '🏭' },
    { id: 'services', label: t('agents.sector.services'), icon: '🛎' },
  ];
}

export function extendedSectorOptions(t: (key: string) => string): ChipOption[] {
  return [
    { id: 'technology', label: t('agents.sector.technology'), icon: '🖥' },
    { id: 'ai', label: t('agents.sector.ai'), icon: '🤖' },
    { id: 'fintech', label: t('agents.sector.fintech'), icon: '💳' },
    { id: 'edtech', label: t('agents.sector.edtech'), icon: '📚' },
    { id: 'healthtech', label: t('agents.sector.healthtech'), icon: '⚕️' },
    { id: 'digital', label: t('agents.sector.digital'), icon: '📱' },
    { id: 'deeptech', label: t('agents.sector.deeptech'), icon: '🔬' },
    { id: 'biotech', label: t('agents.sector.biotech'), icon: '🧬' },
    { id: 'manufacturing', label: t('agents.sector.manufacturing'), icon: '🏭' },
    { id: 'agriculture', label: t('agents.sector.agriculture'), icon: '🌾' },
    { id: 'services', label: t('agents.sector.services'), icon: '🛎' },
  ];
}

export function businessTypeOptions(t: (key: string) => string): ChipOption[] {
  return [
    { id: 'sole_prop', label: t('agents.business_type.sole_prop'), icon: '🏪' },
    { id: 'sdn_bhd', label: t('agents.business_type.sdn_bhd'), icon: '🏢' },
    { id: 'startup', label: t('agents.business_type.startup'), icon: '🚀' },
    { id: 'llp', label: t('agents.business_type.llp'), icon: '🤝' },
    { id: 'cooperative', label: t('agents.business_type.cooperative'), icon: '👥' },
  ];
}
