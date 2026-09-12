import { useEffect, useRef, useState, useCallback } from 'react';
import io, { Socket } from 'socket.io-client';

// WebSocket Event Types (matching backend)
export enum WSEventType {
  PRICE_UPDATE = 'price_update',
  ORDER_BOOK_UPDATE = 'order_book_update',
  TRADING_SIGNAL = 'trading_signal',
  POSITION_UPDATE = 'position_update',
  TRADING_STATUS = 'trading_status',
  SYSTEM_HEALTH = 'system_health',
  ML_PREDICTION = 'ml_prediction'
}

// WebSocket Message Interfaces
export interface WSMessage<T = any> {
  type: WSEventType;
  data: T;
  timestamp: string;
  correlation_id?: string;
}

export interface PriceUpdateMessage {
  symbol: string;
  price: number;
  volume: number;
  change_percent: number;
  bid: number;
  ask: number;
  timestamp: string;
}

export interface OrderBookUpdateMessage {
  symbol: string;
  bids: Array<[price: number, size: number]>;
  asks: Array<[price: number, size: number]>;
  timestamp: string;
}

export interface TradingSignalMessage {
  symbol: string;
  signal_type: 'BUY' | 'SELL' | 'HOLD';
  strength: number;
  confidence: number;
  reasoning: string;
  timestamp: string;
}

export interface PositionUpdateMessage {
  symbol: string;
  quantity: number;
  entry_price: number;
  current_price: number;
  pnl: number;
  pnl_percentage: number;
  timestamp: string;
  action: 'OPEN' | 'UPDATE' | 'CLOSE';
  profit_loss: number;
}

export interface TradingStatusMessage {
  is_active: boolean;
  mode: 'live' | 'simulated';
  strategy: string;
  symbols: string[];
  active_positions: number;
  total_pnl: number;
}

export interface SystemHealthMessage {
  status: 'healthy' | 'warning' | 'critical';
  uptime: number;
  memory_usage: number;
  cpu_usage: number;
  websocket_connections: number;
  last_trading_activity: string;
}

// Hook configuration
interface UseWebSocketOptions {
  url?: string;
  autoConnect?: boolean;
  reconnectionAttempts?: number;
  reconnectionDelay?: number;
  onConnect?: () => void;
  onDisconnect?: (reason: string) => void;
  onError?: (error: Error) => void;
}

// Hook return type
interface UseWebSocketReturn {
  socket: Socket | null;
  connected: boolean;
  connecting: boolean;
  error: string | null;
  reconnect: () => void;
  disconnect: () => void;
  emit: (event: string, data?: any) => void;
  lastMessage: WSMessage | null;
}

const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL || 'http://localhost:8081';

/**
 * Modern WebSocket hook with Socket.IO client integration
 * Provides auto-reconnection, connection status tracking, and proper cleanup
 */
export function useWebSocket(options: UseWebSocketOptions = {}): UseWebSocketReturn {
  const {
    url = WS_BASE_URL,
    autoConnect = true,
    reconnectionAttempts = 5,
    reconnectionDelay = 3000,
    onConnect,
    onDisconnect,
    onError
  } = options;

  const [socket, setSocket] = useState<Socket | null>(null);
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null);

  // Store reconnection timer and attempt counter
  const reconnectionTimerRef = useRef<NodeJS.Timeout | null>(null);
  const attemptRef = useRef(0);
  const socketRef = useRef<Socket | null>(null);

  // Throttle function for performance optimization
  const throttle = useCallback((func: Function, limit: number) => {
    let inThrottle: boolean;
    return function(this: any, ...args: any[]) {
      const context = this;
      if (!inThrottle) {
        func.apply(context, args);
        inThrottle = true;
        setTimeout(() => inThrottle = false, limit);
      }
    };
  }, []);

  const throttledMessageUpdate = useRef(
    throttle((message: WSMessage) => {
      setLastMessage(message);
    }, 100) // Update max once per 100ms
  );

  const connect = useCallback(() => {
    if (socketRef.current?.connected) return;

    setConnecting(true);
    setError(null);

    try {
      const newSocket = io(url, {
        transports: ['websocket', 'polling'],
        upgrade: true,
        rememberUpgrade: true,
        timeout: 10000,
        reconnection: false, // Handle reconnection manually
        forceNew: true,
      });

      socketRef.current = newSocket;

      newSocket.on('connect', () => {
        console.log('✅ WebSocket connected successfully');
        setConnected(true);
        setConnecting(false);
        setError(null);
        attemptRef.current = 0; // Reset attempt counter

        onConnect?.();
      });

      newSocket.on('disconnect', (reason) => {
        console.log('🔌 WebSocket disconnected, reason:', reason);
        setConnected(false);
        setConnecting(false);

        const reasonMessage = getDisconnectReason(reason);
        onDisconnect?.(reasonMessage);

        // Handle auto-reconnection
        if (reason !== 'io client disconnect' && attemptRef.current < reconnectionAttempts) {
          handleReconnection();
        }
      });

      newSocket.on('connect_error', (err) => {
        console.error('🔌 WebSocket connection error:', err);
        setConnected(false);
        setConnecting(false);
        setError(err.message);

        onError?.(err);

        // Handle connection error reconnection
        if (attemptRef.current < reconnectionAttempts) {
          handleReconnection();
        }
      });

      // Handle incoming messages
      Object.values(WSEventType).forEach(eventType => {
        newSocket.on(eventType, (data: any) => {
          const message: WSMessage = {
            type: eventType as WSEventType,
            data,
            timestamp: new Date().toISOString()
          };
          throttledMessageUpdate.current(message);
        });
      });

      setSocket(newSocket);

    } catch (err) {
      console.error('❌ WebSocket initialization error:', err);
      setConnecting(false);
      setError(err instanceof Error ? err.message : 'Connection failed');
    }
  }, [url, reconnectionAttempts, onConnect, onDisconnect, onError]);

  const handleReconnection = useCallback(() => {
    if (reconnectionTimerRef.current) {
      clearTimeout(reconnectionTimerRef.current);
    }

    attemptRef.current += 1;
    const delay = Math.min(reconnectionDelay * Math.pow(1.5, attemptRef.current - 1), 30000);

    console.log(`🔄 Attempting WebSocket reconnection ${attemptRef.current}/${reconnectionAttempts} in ${delay}ms`);

    reconnectionTimerRef.current = setTimeout(() => {
      connect();
    }, delay);
  }, [connect, reconnectionDelay, reconnectionAttempts]);

  const reconnect = useCallback(() => {
    if (reconnectionTimerRef.current) {
      clearTimeout(reconnectionTimerRef.current);
    }
    attemptRef.current = 0; // Reset attempts for manual reconnect
    disconnect();
    connect();
  }, [connect]);

  const disconnect = useCallback(() => {
    if (reconnectionTimerRef.current) {
      clearTimeout(reconnectionTimerRef.current);
      reconnectionTimerRef.current = null;
    }

    if (socketRef.current) {
      console.log('🔌 Manually disconnecting WebSocket');
      socketRef.current.disconnect();
      socketRef.current = null;
    }

    setSocket(null);
    setConnected(false);
    setConnecting(false);
  }, []);

  const emit = useCallback((event: string, data?: any) => {
    if (socketRef.current?.connected) {
      socketRef.current.emit(event, data);
    } else {
      console.warn('⚠️ Cannot emit WebSocket event: not connected');
    }
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    // Cleanup on unmount
    return () => {
      disconnect();
    };
  }, [autoConnect, connect, disconnect]);

  return {
    socket: socketRef.current,
    connected,
    connecting,
    error,
    reconnect,
    disconnect,
    emit,
    lastMessage
  };
}

// Utility function to get human-readable disconnect reason
function getDisconnectReason(reason: string): string {
  switch (reason) {
    case 'io server disconnect':
      return 'Server initiated disconnect';
    case 'io client disconnect':
      return 'Client initiated disconnect';
    case 'ping timeout':
      return 'Connection timeout (ping)';
    case 'transport close':
      return 'Transport connection closed';
    case 'transport error':
      return 'Transport connection error';
    default:
      return `Unknown reason: ${reason}`;
  }
}

/**
 * Hook for subscribing to real-time order book data
 */
export function useRealTimeOrderBook(symbol: string) {
  const { socket, connected, lastMessage } = useWebSocket({
    autoConnect: true
  });

  const [orderBook, setOrderBook] = useState<{
    bids: Array<[price: number, size: number]>;
    asks: Array<[price: number, size: number]>;
    timestamp?: string;
  }>({ bids: [], asks: [] });

  // Subscribe to order book updates
  useEffect(() => {
    if (socket && connected && symbol) {
      console.log(`📊 Subscribing to order book for ${symbol}`);
      socket.emit('subscribe_orderbook', { symbol });
    }

    return () => {
      // Cleanup subscription on unmount or symbol change
      if (socket && connected && symbol) {
        socket.emit('unsubscribe_orderbook', { symbol });
      }
    };
  }, [socket, connected, symbol]);

  // Update order book when messages arrive
  useEffect(() => {
    if (lastMessage?.type === WSEventType.ORDER_BOOK_UPDATE) {
      const update = lastMessage.data as OrderBookUpdateMessage;
      if (update.symbol === symbol) {
        setOrderBook({
          bids: update.bids,
          asks: update.asks,
          timestamp: update.timestamp
        });
      }
    }
  }, [lastMessage, symbol]);

  return {
    orderBook,
    connected,
    lastUpdate: orderBook.timestamp
  };
}

/**
 * Hook for subscribing to real-time price data
 */
export function useRealTimePrice(symbol: string) {
  const { socket, connected, lastMessage } = useWebSocket({
    autoConnect: true
  });

  const [priceData, setPriceData] = useState<PriceUpdateMessage | null>(null);

  // Subscribe to price updates
  useEffect(() => {
    if (socket && connected && symbol) {
      console.log(`💰 Subscribing to price updates for ${symbol}`);
      socket.emit('subscribe_price', { symbol });
    }

    return () => {
      if (socket && connected && symbol) {
        socket.emit('unsubscribe_price', { symbol });
      }
    };
  }, [socket, connected, symbol]);

  // Update price data when messages arrive
  useEffect(() => {
    if (lastMessage?.type === WSEventType.PRICE_UPDATE) {
      const update = lastMessage.data as PriceUpdateMessage;
      if (update.symbol === symbol) {
        setPriceData(update);
      }
    }
  }, [lastMessage, symbol]);

  return {
    priceData,
    connected
  };
}
