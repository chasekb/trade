import type { NextConfig } from "next";

const backendBaseUrl =
  process.env.BACKEND_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  'http://localhost:8081';

const nextConfig: NextConfig = {
  serverExternalPackages: ['ws', 'bufferutil', 'utf-8-validate'],
  experimental: {
    optimizePackageImports: [
      'chart.js',
      'react-chartjs-2',
      '@tanstack/react-query',
      'chartjs-adapter-date-fns',
      'socket.io-client',
      'zustand'
    ],
  },

  // Proxy API routes to backend
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${backendBaseUrl}/api/:path*`
      },
      {
        source: '/ws',
        destination: `${backendBaseUrl}/ws`
      }
    ];
  },

  webpack: (config, { buildId, dev, isServer, defaultLoaders, webpack }) => {
    // Bundle analyzer for production builds
    if (!dev && process.env.ANALYZE === 'true') {
      try {
        const { BundleAnalyzerPlugin } = require('webpack-bundle-analyzer');
        config.plugins.push(
          new BundleAnalyzerPlugin({
            analyzerMode: 'static',
            reportFilename: './analyze/client.html',
            openAnalyzer: false,
          })
        );
      } catch (error) {
        console.warn('webpack-bundle-analyzer not found, skipping bundle analysis');
      }
    }

    // Custom webpack optimizations for trading charts
    if (!isServer) {
      config.resolve.alias = {
        ...config.resolve.alias,
        'chart.js': 'chart.js/auto/auto.js', // Tree-shake Chart.js
      };
    }

    // Optimize bundle splitting
    config.optimization = {
      ...config.optimization,
      splitChunks: {
        chunks: 'all',
        cacheGroups: {
          chartjs: {
            test: /[\\/]node_modules[\\/](chart\.js|react-chartjs-2)[\\/]/,
            name: 'chartjs-vendor',
            chunks: 'all',
            priority: 20,
          },
          socket: {
            test: /[\\/]node_modules[\\/]socket\.io-client[\\/]/,
            name: 'socket-vendor',
            chunks: 'all',
            priority: 15,
          },
          react: {
            test: /[\\/]node_modules[\\/](react|react-dom|@tanstack\/react-query)[\\/]/,
            name: 'react-vendor',
            chunks: 'all',
            priority: 10,
          },
          vendor: {
            test: /[\\/]node_modules[\\/](?!chart\.js|react-chartjs-2|socket\.io-client|react|react-dom|@tanstack)/,
            name: 'vendor',
            chunks: 'all',
            priority: 5,
          },
        },
      },
    };

    return config;
  },

  // Performance optimizations
  images: {
    deviceSizes: [640, 750, 828, 1080, 1200, 1920, 2048, 3840],
    imageSizes: [16, 32, 48, 64, 96, 128, 256, 384],
    formats: ['image/webp', 'image/avif'],
  },

  // Compression and caching
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'DENY'
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff'
          },
          {
            key: 'Referrer-Policy',
            value: 'origin-when-cross-origin'
          }
        ]
      },
      {
        source: '/api/trading/execution-reconciliation',
        headers: [
          {
            key: 'Cache-Control',
            value: 'no-store'
          }
        ]
      },
      {
        source: '/_next/static/(.*)',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=31536000, immutable'
          }
        ]
      }
    ];
  },

  // Output configuration for standalone deployment
  output: 'standalone',

  // Turbopack configuration (empty to allow webpack config)
  turbopack: {},
};

export default nextConfig;
