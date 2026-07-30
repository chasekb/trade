import { getAllSymbols, parseCustomSymbols, resolveUniverseSymbols, symbolsMatch } from './symbolUniverse';

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
});
