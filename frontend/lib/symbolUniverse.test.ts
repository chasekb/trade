import {
  deriveProductCategories,
  getAllSymbols,
  hasUsableProductCategories,
  parseCustomSymbols,
  resolveUniverseSymbols,
  symbolsMatch,
} from './symbolUniverse';

describe('symbol universe helpers', () => {
  const products = {
    all_usd: ['BTC-USD', 'ETH-USD', 'ADA-USD'],
    all_eur: ['BTC-EUR'],
    all_products: ['BTC-USD', 'ETH-USD', 'ADA-USD', 'BTC-EUR', 'ETH-BTC'],
  };

  it('parses custom symbols as the exact typed custom universe instead of the previous predefined universe', () => {
    expect(parseCustomSymbols(' sol-usd, ETH-USD, sol-usd ,, ada-usd ')).toEqual([
      'SOL-USD',
      'ETH-USD',
      'ADA-USD',
    ]);
    expect(parseCustomSymbols('')).toEqual([]);
  });

  it('uses null as the custom-universe sentinel so both trading tabs replace symbols from custom input', () => {
    const previousAllUsd = products.all_usd;
    const customSymbols = parseCustomSymbols('SOL-USD,XRP-USD');

    expect(resolveUniverseSymbols('all_usd', products, getAllSymbols(products))).toBe(previousAllUsd);
    expect(resolveUniverseSymbols('custom', products, getAllSymbols(products))).toBeNull();
    expect(symbolsMatch(customSymbols, previousAllUsd)).toBe(false);
    expect(customSymbols).toEqual(['SOL-USD', 'XRP-USD']);
  });

  it('supports switching predefined universe to custom to another universe and back to custom', () => {
    const allSymbols = ['BTC-USD', 'ETH-USD', 'ADA-USD', 'SOL-USD', 'BTC-EUR', 'ETH-BTC'];
    const firstUniverse = resolveUniverseSymbols('all_usd', null, allSymbols) ?? [];
    const firstCustom = parseCustomSymbols('SOL-USD,XRP-USD');
    const nextUniverse = resolveUniverseSymbols('all_btc', null, allSymbols) ?? [];
    const secondCustom = parseCustomSymbols('DOGE-USD');

    expect(firstUniverse).toEqual(['BTC-USD', 'ETH-USD', 'ADA-USD', 'SOL-USD']);
    expect(firstCustom).toEqual(['SOL-USD', 'XRP-USD']);
    expect(nextUniverse).toEqual(['ETH-BTC']);
    expect(secondCustom).toEqual(['DOGE-USD']);
  });

  it('derives uncapped categories from every online tradable Coinbase product', () => {
    const coinbaseProducts = [
      { id: 'BTC-USD', status: 'online' },
      { id: 'ETH-USD', status: 'online' },
      { id: 'SOL-USD', status: 'online' },
      { id: 'ADA-USD', status: 'online' },
      { id: 'DOT-USD', status: 'online' },
      { id: 'XRP-USD', status: 'online' },
      { id: 'LTC-USD', status: 'online' },
      { id: 'DOGE-USD', status: 'online' },
      { id: 'AVAX-USD', status: 'online' },
      { id: 'LINK-USD', status: 'online' },
      { id: 'BTC-EUR', status: 'online' },
      { id: 'ETH-EUR', status: 'online' },
      { id: 'ETH-BTC', status: 'online' },
      { id: 'SOL-USDT', status: 'online' },
      { id: 'DELISTED-USD', status: 'offline' },
      { id: 'DISABLED-USD', status: 'online', trading_disabled: true },
    ];

    const categories = deriveProductCategories(coinbaseProducts);

    expect(categories.all_products).toHaveLength(14);
    expect(categories.all_products).toContain('SOL-USDT');
    expect(categories.all_usd).toEqual([
      'ADA-USD',
      'AVAX-USD',
      'BTC-USD',
      'DOGE-USD',
      'DOT-USD',
      'ETH-USD',
      'LINK-USD',
      'LTC-USD',
      'SOL-USD',
      'XRP-USD',
    ]);
    expect(categories.all_eur).toEqual(['BTC-EUR', 'ETH-EUR']);
    expect(categories.all_usdt).toEqual(['SOL-USDT']);
    expect(categories.all_btc).toEqual(['ETH-BTC']);
    expect(categories.major).toEqual(['ADA-USD', 'BTC-USD', 'DOT-USD', 'ETH-USD', 'LTC-USD', 'SOL-USD', 'XRP-USD']);
    expect(categories.minor).toEqual(['AVAX-USD', 'DOGE-USD', 'LINK-USD']);
    expect(categories.crypto).toEqual([
      'ADA-USD',
      'BTC-EUR',
      'BTC-USD',
      'DOT-USD',
      'ETH-BTC',
      'ETH-EUR',
      'ETH-USD',
      'SOL-USD',
      'SOL-USDT',
      'XRP-USD',
    ]);
  });

  it('does not impose hidden slice caps on minor or crypto fallback universes', () => {
    const manyMinorUsdSymbols = Array.from({ length: 60 }, (_, index) => `ALT${index + 1}-USD`);
    const manyCryptoSymbols = Array.from({ length: 60 }, (_, index) => `BTC${index + 1}-EUR`);
    const allSymbols = [...manyMinorUsdSymbols, ...manyCryptoSymbols, 'BTC-USD', 'ETH-USD'];

    expect(resolveUniverseSymbols('minor', null, allSymbols)).toEqual(manyMinorUsdSymbols);
    expect(resolveUniverseSymbols('crypto', null, allSymbols)).toHaveLength(62);
  });

  it('rejects aliased backend categories so the hook can derive live Coinbase universes', () => {
    expect(hasUsableProductCategories({
      all_products: ['BTC-USD', 'ETH-USD'],
      all_usd: ['BTC-USD', 'ETH-USD'],
      all_eur: [],
      all_usdt: [],
      all_btc: [],
      major: ['BTC-USD', 'ETH-USD'],
      minor: [],
      crypto: ['BTC-USD', 'ETH-USD'],
    })).toBe(false);

    expect(hasUsableProductCategories({
      all_products: ['BTC-USD', 'ETH-USD', 'BTC-EUR', 'ETH-BTC', 'DOGE-USD'],
      all_usd: ['BTC-USD', 'DOGE-USD', 'ETH-USD'],
      all_eur: ['BTC-EUR'],
      all_usdt: [],
      all_btc: ['ETH-BTC'],
      major: ['BTC-USD', 'ETH-USD'],
      minor: ['DOGE-USD'],
      crypto: ['BTC-EUR', 'BTC-USD', 'ETH-BTC', 'ETH-USD'],
    })).toBe(true);
  });
});
