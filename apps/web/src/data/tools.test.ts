import { describe, expect, it } from 'vitest';

import { CATEGORIES, TOOLS, TOOL_SLUGS, formatBytes, getTool, toolsByCategory } from './tools';

describe('tool catalogue', () => {
  it('lists the canonical tools with unique slugs', () => {
    expect(TOOL_SLUGS).toEqual(TOOLS.map((tool) => tool.slug));
    expect(new Set(TOOL_SLUGS).size).toBe(TOOLS.length);
    // Quais slugs existem é contrato com o canônico do gateway: quem falha por divergência é
    // packages/common/tests/test_spa_catalog_contract.py — assim a lista não vive em três lugares
    // (canônico, este arquivo e o teste).
  });

  it('groups every tool under one of the four categories', () => {
    const ids = CATEGORIES.map((category) => category.id);
    expect(ids).toEqual(['client', 'text', 'vision', 'audio']);

    for (const tool of TOOLS) {
      expect(ids).toContain(tool.category);
    }
    const total = CATEGORIES.reduce(
      (count, category) => count + toolsByCategory(category.id).length,
      0,
    );
    expect(total).toBe(TOOLS.length);
  });

  it('marks translate as implemented and the client-side apps as browser-only', () => {
    expect(getTool('translate')?.implemented).toBe(true);
    expect(getTool('translate')?.beta).toBe(false);

    for (const slug of ['louder', 'qrcode', 'imposition']) {
      expect(getTool(slug)?.route).toBe('client');
      expect(getTool(slug)?.beta).toBe(false);
      expect(getTool(slug)?.category).toBe('client');
    }
  });

  it('marks every gateway tool as implemented (providers may be unavailable at runtime)', () => {
    for (const tool of TOOLS) {
      if (tool.route === 'gateway') {
        expect(tool.implemented).toBe(true);
        expect(tool.beta).toBe(false);
      }
    }
  });

  it('gives every tool a name, description, icon and limit', () => {
    for (const tool of TOOLS) {
      expect(tool.name).toBeTruthy();
      expect(tool.description.length).toBeGreaterThan(10);
      expect(tool.icon).toBeTruthy();
      expect(tool.maxBytes).toBeGreaterThan(0);
    }
  });

  it('returns undefined for an unknown slug', () => {
    expect(getTool('does-not-exist')).toBeUndefined();
  });
});

describe('formatBytes', () => {
  it('formats KB and MB values', () => {
    expect(formatBytes(1024)).toBe('1 KB');
    expect(formatBytes(10 * 1024 * 1024)).toBe('10 MB');
    expect(formatBytes(1.5 * 1024 * 1024)).toBe('1.5 MB');
  });
});
