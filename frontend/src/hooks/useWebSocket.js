import { useEffect, useRef, useCallback } from 'react';

const API = process.env.REACT_APP_BACKEND_URL || '';

/**
 * Reusable WebSocket hook for real-time messaging.
 * 
 * @param {string} path - WebSocket path (e.g., "/ws/trade/trd_123")
 * @param {function} onMessage - Callback when a message is received (receives parsed JSON)
 * @param {object} options - { enabled: true/false, reconnectInterval: 3000 }
 */
export function useWebSocket(path, onMessage, options = {}) {
  const { enabled = true, reconnectInterval = 3000 } = options;
  const wsRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const onMessageRef = useRef(onMessage);
  const mountedRef = useRef(true);

  // Keep callback ref up to date without triggering reconnect
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  const connect = useCallback(() => {
    if (!enabled || !path || !mountedRef.current) return;

    // Build WebSocket URL
    const wsUrl = API.replace('https://', 'wss://').replace('http://', 'ws://').replace('/api', '');
    const fullUrl = `${wsUrl}${path}`;

    try {
      const ws = new WebSocket(fullUrl);

      ws.onopen = () => {
        // Send periodic pings to keep alive
        if (wsRef.current === ws) {
          const pingInterval = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
              ws.send('ping');
            } else {
              clearInterval(pingInterval);
            }
          }, 25000);
          ws._pingInterval = pingInterval;
        }
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'pong') return; // Ignore pong responses
          if (onMessageRef.current) {
            onMessageRef.current(data);
          }
        } catch (e) {
          // Non-JSON message, ignore
        }
      };

      ws.onclose = () => {
        if (ws._pingInterval) clearInterval(ws._pingInterval);
        if (mountedRef.current && enabled) {
          reconnectTimerRef.current = setTimeout(connect, reconnectInterval);
        }
      };

      ws.onerror = () => {
        ws.close();
      };

      wsRef.current = ws;
    } catch (e) {
      // WebSocket creation failed, retry
      if (mountedRef.current && enabled) {
        reconnectTimerRef.current = setTimeout(connect, reconnectInterval);
      }
    }
  }, [path, enabled, reconnectInterval]);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (wsRef.current) {
        if (wsRef.current._pingInterval) clearInterval(wsRef.current._pingInterval);
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  return wsRef;
}

export default useWebSocket;
