// Shared Malaysian state/federal-territory id list — same ids
// welfare-eligibility's own STATE_IDS uses, and the same i18n label keys
// (agents.welfare-eligibility.state.*) every consumer reads labels from.
// Centralised here so a second/third consumer (the landing hero's Merdeka
// state picker, chat's post-answer state-narrowing chip) doesn't
// duplicate the list — one canonical set of ids, reused wherever a
// "pick your state" control is needed.
export const MALAYSIA_STATE_IDS = [
  'johor', 'kedah', 'kelantan', 'melaka', 'negeri_sembilan', 'pahang',
  'penang', 'perak', 'perlis', 'sabah', 'sarawak', 'selangor', 'terengganu',
  'kl', 'labuan', 'putrajaya',
] as const;

export type MalaysiaStateId = (typeof MALAYSIA_STATE_IDS)[number];
