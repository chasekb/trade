/**
 * Test script for loadCurrentPriceData fallback mechanism and refresh sequence
 * This script tests the fallback from real-time data to historical data
 * and verifies that current price and 24h volume match the current symbol
 */

class PriceDataTester {
    constructor() {
        this.testResults = [];
        this.symbols = ['BTC-USD', 'ETH-USD', 'ADA-USD', 'SOL-USD', 'DOT-USD'];
        this.currentSymbol = 'BTC-USD';
        this.testMode = 'real-time'; // 'real-time', 'fallback', 'error'
    }

    /**
     * Simulate the loadCurrentPriceData function with different scenarios
     */
    async loadCurrentPriceData(symbol, testMode = 'real-time') {
        console.log(`\n🔄 Testing loadCurrentPriceData for ${symbol} in ${testMode} mode`);
        
        try {
            // Test real-time data first
            const realTimeResponse = await fetch(`/api/real-time-data?product_id=${symbol}`);
            const realTimeData = await realTimeResponse.json();
            
            console.log('📡 Real-time data response:', realTimeData);
            
            if (realTimeData && !realTimeData.error && realTimeData.ticker && testMode !== 'fallback') {
                // Use real-time data if available
                const price = parseFloat(realTimeData.ticker.price || 0);
                const volume = parseFloat(realTimeData.ticker.volume_24h || 0);
                const change24h = parseFloat(realTimeData.ticker.price_change_24h || 0);
                
                console.log(`✅ Using real-time data for ${symbol}:`, {
                    price: `$${price.toFixed(2)}`,
                    volume: volume.toLocaleString(),
                    change24h: `${change24h.toFixed(2)}%`
                });
                
                return {
                    source: 'real-time',
                    symbol: symbol,
                    price: price,
                    volume: volume,
                    change24h: change24h,
                    timestamp: new Date().toISOString()
                };
            } else {
                // Fallback: get latest data from historical data API
                console.log(`🔄 No real-time data for ${symbol}, using historical data fallback`);
                const historicalResponse = await fetch(`/api/historical-data?product_id=${symbol}&days=1`);
                const historicalData = await historicalResponse.json();
                
                console.log('📊 Historical data response length:', historicalData?.length || 0);
                
                if (Array.isArray(historicalData) && historicalData.length > 0) {
                    // Get the most recent data point
                    const latestData = historicalData[historicalData.length - 1];
                    const price = parseFloat(latestData.price || 0);
                    const volume = parseFloat(latestData.volume || 0);
                    
                    console.log(`✅ Using historical data for ${symbol}:`, {
                        price: `$${price.toFixed(2)}`,
                        volume: volume.toLocaleString(),
                        dataPoint: latestData
                    });
                    
                    return {
                        source: 'historical',
                        symbol: symbol,
                        price: price,
                        volume: volume,
                        change24h: null,
                        timestamp: new Date().toISOString(),
                        dataPoint: latestData
                    };
                } else {
                    console.warn(`❌ No data available for ${symbol}`);
                    return {
                        source: 'none',
                        symbol: symbol,
                        price: 0,
                        volume: 0,
                        change24h: null,
                        timestamp: new Date().toISOString(),
                        error: 'No data available'
                    };
                }
            }
        } catch (error) {
            console.error(`❌ Failed to load current price data for ${symbol}:`, error);
            return {
                source: 'error',
                symbol: symbol,
                price: 0,
                volume: 0,
                change24h: null,
                timestamp: new Date().toISOString(),
                error: error.message
            };
        }
    }

    /**
     * Test the fallback mechanism by simulating different scenarios
     */
    async testFallbackMechanism() {
        console.log('\n🧪 Testing Fallback Mechanism');
        console.log('=' .repeat(50));
        
        for (const symbol of this.symbols) {
            console.log(`\n📈 Testing symbol: ${symbol}`);
            
            // Test 1: Normal real-time data
            const realTimeResult = await this.loadCurrentPriceData(symbol, 'real-time');
            this.testResults.push(realTimeResult);
            
            // Test 2: Force fallback to historical data
            const fallbackResult = await this.loadCurrentPriceData(symbol, 'fallback');
            this.testResults.push(fallbackResult);
            
            // Test 3: Test with invalid symbol (should trigger error handling)
            const errorResult = await this.loadCurrentPriceData('INVALID-SYMBOL', 'real-time');
            this.testResults.push(errorResult);
            
            // Wait between tests to avoid rate limiting
            await new Promise(resolve => setTimeout(resolve, 1000));
        }
    }

    /**
     * Create a refresh sequence that checks current price and volume match
     */
    async createRefreshSequence() {
        console.log('\n🔄 Creating Refresh Sequence');
        console.log('=' .repeat(50));
        
        const refreshSequence = [];
        
        for (const symbol of this.symbols) {
            console.log(`\n🔄 Refreshing data for ${symbol}`);
            
            // Get current data
            const currentData = await this.loadCurrentPriceData(symbol);
            
            // Verify data integrity
            const verification = this.verifyDataIntegrity(currentData, symbol);
            
            refreshSequence.push({
                symbol: symbol,
                timestamp: new Date().toISOString(),
                data: currentData,
                verification: verification,
                status: verification.isValid ? 'PASS' : 'FAIL'
            });
            
            console.log(`📊 Verification for ${symbol}:`, verification);
            
            // Wait between refreshes
            await new Promise(resolve => setTimeout(resolve, 2000));
        }
        
        return refreshSequence;
    }

    /**
     * Verify that the data matches the expected symbol and is valid
     */
    verifyDataIntegrity(data, expectedSymbol) {
        const verification = {
            isValid: true,
            errors: [],
            warnings: []
        };
        
        // Check symbol match
        if (data.symbol !== expectedSymbol) {
            verification.isValid = false;
            verification.errors.push(`Symbol mismatch: expected ${expectedSymbol}, got ${data.symbol}`);
        }
        
        // Check price validity
        if (data.price <= 0) {
            verification.isValid = false;
            verification.errors.push(`Invalid price: ${data.price}`);
        } else if (data.price < 1) {
            verification.warnings.push(`Very low price: ${data.price} - might be invalid`);
        }
        
        // Check volume validity
        if (data.volume < 0) {
            verification.isValid = false;
            verification.errors.push(`Invalid volume: ${data.volume}`);
        } else if (data.volume === 0) {
            verification.warnings.push(`Zero volume - might indicate no trading activity`);
        }
        
        // Check data source
        if (data.source === 'error') {
            verification.isValid = false;
            verification.errors.push(`Data source error: ${data.error}`);
        } else if (data.source === 'none') {
            verification.isValid = false;
            verification.errors.push(`No data available for symbol`);
        }
        
        // Check timestamp freshness
        const dataAge = Date.now() - new Date(data.timestamp).getTime();
        if (dataAge > 300000) { // 5 minutes
            verification.warnings.push(`Data is ${Math.round(dataAge / 1000)}s old`);
        }
        
        return verification;
    }

    /**
     * Generate a comprehensive test report
     */
    generateTestReport() {
        console.log('\n📋 Test Report');
        console.log('=' .repeat(50));
        
        const totalTests = this.testResults.length;
        const passedTests = this.testResults.filter(r => r.source !== 'error' && r.source !== 'none').length;
        const failedTests = totalTests - passedTests;
        
        console.log(`📊 Total Tests: ${totalTests}`);
        console.log(`✅ Passed: ${passedTests}`);
        console.log(`❌ Failed: ${failedTests}`);
        console.log(`📈 Success Rate: ${((passedTests / totalTests) * 100).toFixed(2)}%`);
        
        // Group by source
        const sourceStats = this.testResults.reduce((acc, result) => {
            acc[result.source] = (acc[result.source] || 0) + 1;
            return acc;
        }, {});
        
        console.log('\n📊 Data Source Statistics:');
        Object.entries(sourceStats).forEach(([source, count]) => {
            console.log(`  ${source}: ${count} tests`);
        });
        
        // Show failed tests
        const failedResults = this.testResults.filter(r => r.source === 'error' || r.source === 'none');
        if (failedResults.length > 0) {
            console.log('\n❌ Failed Tests:');
            failedResults.forEach(result => {
                console.log(`  ${result.symbol}: ${result.source} - ${result.error || 'No data'}`);
            });
        }
        
        return {
            totalTests,
            passedTests,
            failedTests,
            successRate: (passedTests / totalTests) * 100,
            sourceStats,
            failedResults
        };
    }

    /**
     * Run the complete test suite
     */
    async runCompleteTest() {
        console.log('🚀 Starting Complete Price Data Test Suite');
        console.log('=' .repeat(60));
        
        try {
            // Test fallback mechanism
            await this.testFallbackMechanism();
            
            // Create refresh sequence
            const refreshSequence = await this.createRefreshSequence();
            
            // Generate report
            const report = this.generateTestReport();
            
            console.log('\n🎯 Test Complete!');
            console.log('=' .repeat(60));
            
            return {
                testResults: this.testResults,
                refreshSequence: refreshSequence,
                report: report
            };
            
        } catch (error) {
            console.error('❌ Test suite failed:', error);
            throw error;
        }
    }
}

// Export for use in browser console or Node.js
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PriceDataTester;
} else {
    // Browser environment
    window.PriceDataTester = PriceDataTester;
}

// Auto-run if in browser
if (typeof window !== 'undefined') {
    console.log('🔧 Price Data Tester loaded. Run: const tester = new PriceDataTester(); await tester.runCompleteTest();');
}
