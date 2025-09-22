"""
Utility to fetch and manage available trading products from Coinbase Advanced Trading API.
"""

import asyncio
import aiohttp
import json
import logging
from typing import List, Dict, Set
from datetime import datetime

logger = logging.getLogger(__name__)

class ProductFetcher:
    """Fetches and manages available trading products from Coinbase API."""
    
    def __init__(self):
        self.base_url = "https://api.exchange.coinbase.com"
        self.products_cache = []
        self.last_updated = None
    
    async def fetch_all_products(self) -> List[Dict]:
        """Fetch all available products from Coinbase API."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/products") as response:
                    if response.status == 200:
                        products = await response.json()
                        self.products_cache = products
                        self.last_updated = datetime.now()
                        logger.info(f"Fetched {len(products)} products from Coinbase API")
                        return products
                    else:
                        logger.error(f"Failed to fetch products: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Error fetching products: {e}")
            return []
    
    def get_usd_pairs(self) -> List[str]:
        """Get all USD trading pairs."""
        if not self.products_cache:
            return []
        
        usd_pairs = []
        for product in self.products_cache:
            if (product.get('status') == 'online' and 
                product.get('id', '').endswith('-USD') and
                product.get('quote_currency') == 'USD'):
                usd_pairs.append(product['id'])
        
        return sorted(usd_pairs)
    
    def get_major_pairs(self) -> List[str]:
        """Get major trading pairs (BTC, ETH, and other high-volume pairs)."""
        major_symbols = {
            'BTC-USD', 'ETH-USD', 'SOL-USD', 'ADA-USD', 'DOT-USD', 
            'AVAX-USD', 'MATIC-USD', 'LINK-USD', 'UNI-USD', 'LTC-USD',
            'BCH-USD', 'XRP-USD', 'DOGE-USD', 'SHIB-USD', 'ATOM-USD',
            'NEAR-USD', 'ALGO-USD', 'ICP-USD', 'FIL-USD', 'VET-USD',
            'TRX-USD', 'ETC-USD', 'XLM-USD', 'XTZ-USD', 'ZEC-USD'
        }
        
        usd_pairs = self.get_usd_pairs()
        major_pairs = [pair for pair in usd_pairs if pair in major_symbols]
        return sorted(major_pairs)
    
    def get_stablecoin_pairs(self) -> List[str]:
        """Get stablecoin trading pairs."""
        stablecoin_symbols = {
            'USDT-USD', 'USDC-USD', 'DAI-USD', 'BUSD-USD', 'TUSD-USD'
        }
        
        usd_pairs = self.get_usd_pairs()
        stablecoin_pairs = [pair for pair in usd_pairs if pair in stablecoin_symbols]
        return sorted(stablecoin_pairs)
    
    def get_dex_tokens(self) -> List[str]:
        """Get DEX and DeFi token pairs."""
        dex_keywords = ['UNI', 'SUSHI', 'CAKE', 'CRV', 'COMP', 'AAVE', 'MKR', 'SNX', 'YFI']
        
        usd_pairs = self.get_usd_pairs()
        dex_pairs = []
        for pair in usd_pairs:
            for keyword in dex_keywords:
                if keyword in pair:
                    dex_pairs.append(pair)
                    break
        
        return sorted(dex_pairs)
    
    def get_meme_tokens(self) -> List[str]:
        """Get meme token pairs."""
        meme_keywords = ['DOGE', 'SHIB', 'PEPE', 'FLOKI', 'BONK', 'WIF', 'POPCAT', 'TOSHI']
        
        usd_pairs = self.get_usd_pairs()
        meme_pairs = []
        for pair in usd_pairs:
            for keyword in meme_keywords:
                if keyword in pair:
                    meme_pairs.append(pair)
                    break
        
        return sorted(meme_pairs)
    
    def get_products_by_quote_currency(self, quote_currency: str) -> List[str]:
        """Get all products for a specific quote currency."""
        if not self.products_cache:
            return []
        
        products = []
        for product in self.products_cache:
            if (product.get('status') == 'online' and 
                not product.get('trading_disabled', False) and
                product.get('quote_currency') == quote_currency):
                products.append(product['id'])
        
        return sorted(products)
    
    def get_all_products(self) -> List[str]:
        """Get all available product IDs."""
        if not self.products_cache:
            return []
        
        all_products = []
        for product in self.products_cache:
            if product.get('status') == 'online' and not product.get('trading_disabled', False):
                all_products.append(product['id'])
        
        return sorted(all_products)
    
    def get_products_by_category(self) -> Dict[str, List[str]]:
        """Get products organized by category."""
        categories = {
            'major': self.get_major_pairs(),
            'stablecoins': self.get_stablecoin_pairs(),
            'dex_tokens': self.get_dex_tokens(),
            'meme_tokens': self.get_meme_tokens(),
            'all_usd': self.get_usd_pairs(),
            'all_products': self.get_all_products()
        }
        
        # Add dynamic categories for each quote currency
        quote_currencies = ['USD', 'USDT', 'EUR', 'BTC', 'GBP', 'USDC', 'ETH', 'DAI']
        for currency in quote_currencies:
            products = self.get_products_by_quote_currency(currency)
            if products:
                categories[f'all_{currency.lower()}'] = products
        
        return categories
    
    def save_products_to_file(self, filename: str = "available_products.json"):
        """Save products to a JSON file."""
        try:
            products_data = {
                'last_updated': self.last_updated.isoformat() if self.last_updated else None,
                'total_products': len(self.products_cache),
                'categories': self.get_products_by_category()
            }
            
            with open(filename, 'w') as f:
                json.dump(products_data, f, indent=2)
            
            logger.info(f"Saved products to {filename}")
            return True
        except Exception as e:
            logger.error(f"Error saving products: {e}")
            return False

async def main():
    """Main function to fetch and display products."""
    fetcher = ProductFetcher()
    
    print("🔄 Fetching products from Coinbase Advanced Trading API...")
    products = await fetcher.fetch_all_products()
    
    if products:
        print(f"✅ Fetched {len(products)} products")
        
        categories = fetcher.get_products_by_category()
        
        print("\n📊 Product Categories:")
        print("=" * 50)
        for category, pairs in categories.items():
            print(f"{category.replace('_', ' ').title()}: {len(pairs)} pairs")
            if len(pairs) <= 10:  # Show all if 10 or fewer
                for pair in pairs:
                    print(f"  - {pair}")
            else:  # Show first 10 if more
                for pair in pairs[:10]:
                    print(f"  - {pair}")
                print(f"  ... and {len(pairs) - 10} more")
            print()
        
        # Save to file
        if fetcher.save_products_to_file():
            print("💾 Products saved to available_products.json")
        
        return categories
    else:
        print("❌ Failed to fetch products")
        return None

if __name__ == "__main__":
    asyncio.run(main())
