import { defaultServiceNav, type ServiceNavItem } from '@agenteresolve/ui';

/** Header navigation: catalog home followed by the cross-service links. */
export const SERVICE_NAV: ServiceNavItem[] = [
  { label: 'Catálogo', href: '/' },
  ...defaultServiceNav,
];
