import { UniverseType } from '@/types/trading';

export const FALLBACK_COINBASE_SYMBOLS = ['BTC-USD', 'ETH-USD', 'ADA-USD', 'SOL-USD', 'DOT-USD', 'XRP-USD'];
export const PRODUCT_UNIVERSE_KEYS: UniverseType[] = [
  'all_products',
  'all_usd',
  'all_eur',
  'all_usdt',
  'all_btc',
  'major',
  'minor',
  'crypto',
  'custom',
];

const MAJOR_PRODUCT_IDS = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'ADA-USD', 'DOT-USD', 'XRP-USD', 'LTC-USD'];
const CRYPTO_SYMBOL_FRAGMENTS = ['BTC', 'ETH', 'ADA', 'SOL', 'DOT', 'XRP'];

export type CoinbaseProductLike = {
  id?: string;
  product_id?: string;
  status?: string;
  trading_disabled?: boolean;
  base_currency?: string;
  quote_currency?: string;
};

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

function quoteCurrency(symbol: string): string {
  const lastDash = symbol.lastIndexOf('-');
  return lastDash >= 0 ? symbol.slice(lastDash + 1) : '';
}

function isOnlineTradableProduct(product: CoinbaseProductLike): boolean {
  return typeof (product.id ?? product.product_id) === 'string' &&
    product.status === 'online' &&
    product.trading_disabled !== true;
}

export function deriveProductCategories(products: CoinbaseProductLike[]): Record<string, string[]> {
  const seen = new Set<string>();
  const allProducts = products
    .filter(isOnlineTradableProduct)
    .map((product) => (product.id ?? product.product_id ?? '').toUpperCase())
    .filter((symbol) => {
      if (!symbol || seen.has(symbol)) return false;
      seen.add(symbol);
      return true;
    })
    .sort();

  return {
    all_products: allProducts,
    all_usd: allProducts.filter((symbol) => quoteCurrency(symbol) === 'USD'),
    all_eur: allProducts.filter((symbol) => quoteCurrency(symbol) === 'EUR'),
    all_usdt: allProducts.filter((symbol) => quoteCurrency(symbol) === 'USDT'),
    all_btc: allProducts.filter((symbol) => quoteCurrency(symbol) === 'BTC'),
    major: allProducts.filter((symbol) => MAJOR_PRODUCT_IDS.includes(symbol)),
    minor: allProducts.filter((symbol) => quoteCurrency(symbol) === 'USD' && !MAJOR_PRODUCT_IDS.includes(symbol)),
    crypto: allProducts.filter((symbol) => CRYPTO_SYMBOL_FRAGMENTS.some((fragment) => symbol.includes(fragment))),
  };
}

function hasAllUniverseKeys(products: Record<string, string[]>): boolean {
  return PRODUCT_UNIVERSE_KEYS
    .filter((key) => key !== 'custom')
    .every((key) => Array.isArray(products[key]));
}

function arraysEqual(left: string[] | undefined, right: string[] | undefined): boolean {
  if (!left || !right) return false;
  return left.length === right.length && left.every((symbol, index) => symbol === right[index]);
}

export function hasUsableProductCategories(products: Record<string, string[]> | null | undefined): boolean {
  if (!products || !hasAllUniverseKeys(products)) return false;
  const allProducts = products.all_products ?? [];
  if (allProducts.length === 0) return false;
  // A backend that aliases the complete product list to a narrower universe is
  // not a usable category contract. The UI should derive uncapped categories
  // from the live Coinbase products instead of silently reusing one list.
  if (arraysEqual(products.all_products, products.all_usd) || arraysEqual(products.all_products, products.major)) {
    return false;
  }
  return true;
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
    case 'major':
      return allSymbols.filter((symbol) => MAJOR_PRODUCT_IDS.includes(symbol));
    case 'minor':
      return allSymbols
        .filter(
          (symbol) =>
            quoteCurrency(symbol) === 'USD' &&
            !MAJOR_PRODUCT_IDS.includes(symbol)
        );
    case 'crypto':
      return allSymbols.filter((symbol) => CRYPTO_SYMBOL_FRAGMENTS.some((fragment) => symbol.includes(fragment)));
    default:
      return [];
  }
}
