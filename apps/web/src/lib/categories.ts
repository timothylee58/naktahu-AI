export type CategoryId = 'tax' | 'biz' | 'docs' | 'civic';
export type CategoryIcon = 'Wallet' | 'Briefcase' | 'IdCard' | 'Landmark';

export interface Category {
  id: CategoryId;
  icon: CategoryIcon;
  /** i18n keys, resolved by the component so locale switches stay live. */
  chips: readonly [string, string, string];
}

export const CATEGORIES: readonly Category[] = [
  { id: 'tax', icon: 'Wallet', chips: ['chip.tax.1', 'chip.tax.2', 'chip.tax.3'] },
  { id: 'biz', icon: 'Briefcase', chips: ['chip.biz.1', 'chip.biz.2', 'chip.biz.3'] },
  { id: 'docs', icon: 'IdCard', chips: ['chip.docs.1', 'chip.docs.2', 'chip.docs.3'] },
  { id: 'civic', icon: 'Landmark', chips: ['chip.civic.1', 'chip.civic.2', 'chip.civic.3'] },
];
