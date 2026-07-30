import { UniverseType } from '@/types/trading';

export const FALLBACK_COINBASE_SYMBOLS = ['BTC-USD', 'ETH-USD', 'ADA-USD', 'SOL-USD', 'DOT-USD', 'XRP-USD'];

export function parseCustomSymbols(input: string): string[] {
  const seen = new Set<string>();
  const symbols: string[] = [];

  input
    .split(',')
    .map((symbol) => symbol.trim().toUpperCase())
    .filter(Boolean)
    .forEach((symbol) => {
      if (!seen.has(symbol)) {
        seen.add(symbol);
        symbols.push(symbol);
      }
    });

  return symbols;
}

export function symbolsMatch(left: string[], right: string[]): boolean {
  return left.length === right.length && left.every((symbol, index) => symbol === right[index]);
}

export function getAllSymbols(products: Record<string, string[]> | null | undefined): string[] {
  if (!products) return [];

  const seen = new Set<string>();
  return Object.values(products)
    .flat()
    .filter((symbol) => {
      if (seen.has(symbol)) return false;
      seen.add(symbol);
      return true;
    });
}

export function resolveUniverseSymbols(
  universeType: UniverseType | string,
  products: Record<string, string[]> | null | undefined,
  allSymbols: string[]
): string[] | null {
  if (universeType === 'custom') {
    return null;
  }

  if (products && products[universeType]) {
    return products[universeType];
  }

  switch (universeType) {
    case 'all_products':
      return allSymbols;
    case 'all_usd':
      return allSymbols.filter((symbol) => symbol.endsWith('-USD'));
    case 'all_eur':
      return allSymbols.filter((symbol) => symbol.endsWith('-EUR'));
    case 'all_usdt':
      return allSymbols.filter((symbol) => symbol.endsWith('-USDT'));
    case 'all_btc':
      return allSymbols.filter((symbol) => symbol.endsWith('-BTC'));
    case 'major': {
      const majorPairs = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'ADA-USD', 'DOT-USD', 'XRP-USD', 'LTC-USD'];
      return allSymbols.filter((symbol) => majorPairs.includes(symbol));
    }
    case 'minor':
      return allSymbols
        .filter(
          (symbol) =>
            symbol.endsWith('-USD') &&
            !['EUR-USD', 'GBP-USD', 'AUD-USD', 'NZD-USD'].includes(symbol) &&
            !symbol.includes('BTC') &&
            !symbol.includes('ETH')
        )
        .slice(0, 21);
    case 'crypto':
      return allSymbols
        .filter(
          (symbol) =>
            symbol.includes('BTC') ||
            symbol.includes('ETH') ||
            symbol.includes('ADA') ||
            symbol.includes('SOL') ||
            symbol.includes('DOT') ||
            symbol.includes('XRP')
        )
        .slice(0, 35);
    default:
      return [];
  }
}
